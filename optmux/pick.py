"""optmux pick: choose a known project (live TMUX session or not) and drop into it.

Every project has its own TMUX server, so there is no global view of what's running. A small registry
of projects optmux was started in (updated on every start) stands in for it, and each entry's socket
tells whether its server is up.
"""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

EXIT_CANCELLED = 130
EXIT_NOTHING = 1

LIST_SESSIONS_FORMAT = "#{session_name}\t#{session_windows}\t#{session_attached}\t#{session_activity}"
LIST_WINDOWS_FORMAT = "#I #{b:pane_current_path} #{?window_bell_flag,[bell],}"


@dataclass
class Project:
    last_used: int
    kind: str  # "yaml" or "dir"
    target: str  # absolute path of the YAML file or directory
    session: str
    sock: str
    windows: int = 0  # filled in by liveness checks
    attached: int = 0
    activity: int = 0
    live: bool = False

    @property
    def label(self):
        """What to show for the project: its directory (or YAML's directory) with the session name."""
        base = Path(self.target)
        where = base if self.kind == "dir" else base.parent
        return f"{self.session}  {tilde(where)}" + (f"  ({base.name})" if self.kind == "yaml" else "")


def tilde(path):
    home = str(Path.home())
    s = str(path)
    return "~" + s[len(home):] if s == home or s.startswith(home + os.sep) else s


def registry_path():
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "optmux" / "projects.tsv"


def _parse_line(line):
    parts = line.rstrip("\n").split("\t")
    if len(parts) != 5 or parts[1] not in ("yaml", "dir"):
        return None
    try:
        return Project(int(parts[0]), parts[1], parts[2], parts[3], parts[4])
    except ValueError:
        return None


def load_registry():
    try:
        lines = registry_path().read_text().splitlines()
    except OSError:
        return []
    return [p for p in map(_parse_line, lines) if p]


def save_registry(projects):
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".projects.")
    with os.fdopen(fd, "w") as f:
        for p in projects:
            f.write(f"{p.last_used}\t{p.kind}\t{p.target}\t{p.session}\t{p.sock}\n")
    os.replace(tmp, path)


def record_project(kind, target, session, sock, now=None):
    """Upsert a project (identified by its absolute target) as just used; prune vanished ones."""
    target = str(target)
    entry = Project(int(now if now is not None else time.time()), kind, target, session, str(sock))
    projects = [p for p in load_registry() if p.target != target and Path(p.target).exists()]
    projects.append(entry)
    save_registry(projects)


def forget_project(target):
    target = str(Path(target).resolve()) if Path(target).exists() else str(target)
    save_registry([p for p in load_registry() if p.target != target])


def probe(project):
    """Fill in the project's live state from its TMUX server; not running leaves it not live."""
    try:
        out = subprocess.run(
            ["tmux", "-S", project.sock, "list-sessions", "-F", LIST_SESSIONS_FORMAT],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return project
    if out.returncode != 0:
        return project
    for line in out.stdout.splitlines():
        name, windows, attached, activity = (line.split("\t") + ["0"] * 4)[:4]
        if name == project.session:
            project.live = True
            project.windows = int(windows or 0)
            project.attached = int(attached or 0)
            project.activity = int(activity or 0)
    return project


def pickable():
    """Projects whose target still exists: live ones first (latest activity), then by last use."""
    projects = [probe(p) for p in load_registry() if Path(p.target).exists()]
    projects.sort(key=lambda p: (not p.live, -(p.activity if p.live else p.last_used)))
    return projects


def describe(project):
    if not project.live:
        return "-"
    state = f"{project.windows} windows"
    return state + (", attached" if project.attached else "")


def list_lines(projects):
    """TSV for scripts: state, kind, target, session, socket."""
    return [
        "\t".join(["live" if p.live else "idle", p.kind, p.target, p.session, p.sock])
        for p in projects
    ]


def launch_command(project):
    """argv that starts or attaches the project, as a child process."""
    return [sys.executable, "-c", "from optmux.cli import main; main()", project.target, "start"]


def self_command(*args):
    # fzf placeholders like {1} are left for fzf to quote
    quoted = [a if a.startswith("{") else shlex.quote(a) for a in args]
    return " ".join([shlex.quote(sys.executable), "-c", shlex.quote("from optmux.cli import main; main()"), *quoted])


def fzf_rows(projects):
    """Rows for fzf: target, socket, session, then the visible text."""
    return [
        "\t".join([p.target, p.sock, p.session, f"{'●' if p.live else '○'} {p.label}  {describe(p)}"])
        for p in projects
    ]


def choose_with_fzf(projects):
    """Run fzf over the projects (already filtered by the query); returns the chosen target, or None when cancelled."""
    preview = (
        f"tmux -S {{2}} list-windows -t {{3}} -F {shlex.quote(LIST_WINDOWS_FORMAT)} 2>/dev/null"
        " || echo '(not running)'"
    )
    cmd = [
        "fzf", "--delimiter", "\t", "--with-nth", "4", "--no-sort", "--ansi",
        "--header", "enter: attach/start   ctrl-x: stop   ctrl-d: forget",
        "--preview", preview, "--preview-window", "right,40%",
        "--bind", f"ctrl-x:execute-silent({self_command('{1}', 'stop')})+reload({self_command('pick', '--rows')})",
        "--bind", f"ctrl-d:execute-silent({self_command('pick', '--forget', '{1}')})+reload({self_command('pick', '--rows')})",
    ]
    result = subprocess.run(cmd, input="\n".join(fzf_rows(projects)) + "\n", stdout=subprocess.PIPE, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split("\n")[0].split("\t")[0]


def choose_with_menu(projects):
    """Numbered-menu fallback when fzf is missing."""
    for i, p in enumerate(projects, 1):
        print(f"{i:3}) {'●' if p.live else '○'} {p.label}  {describe(p)}", file=sys.stderr)
    try:
        answer = input("pick> ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if answer.isdigit() and 1 <= int(answer) <= len(projects):
        return projects[int(answer) - 1].target
    return None


USAGE = """\
usage: optmux pick [--list] [--live] [-1] [QUERY]

  Choose a project optmux has been started in, and attach to (or start) its TMUX session.
  Returns when you detach or exit, so it can be run in a loop.
  ● has a running session, ○ doesn't. Inside the picker:
  enter attaches or starts, ctrl-x stops the session, ctrl-d forgets the project.

  --list      print projects as TSV (state, kind, target, session, socket) and exit
  --live      only projects with a running session
  -1          if exactly one project matches QUERY, pick it without asking

exit status: 0 after attach/detach, 130 cancelled, 1 nothing to pick
"""


def run(argv):
    """The `optmux pick` command; returns the exit status."""
    list_only = live_only = auto_single = False
    query = []
    select = None  # hidden, for tests: pick the Nth project without any UI
    rows = False  # hidden, for the picker's reload
    forget = None
    args = list(argv)
    while args:
        a = args.pop(0)
        if a in ("-h", "--help"):
            print(USAGE)
            return 0
        elif a == "--list":
            list_only = True
        elif a == "--live":
            live_only = True
        elif a == "-1":
            auto_single = True
        elif a == "--select":
            select = int(args.pop(0))
        elif a == "--rows":
            rows = True
        elif a == "--forget":
            forget = args.pop(0)
        else:
            query.append(a)

    if forget is not None:
        forget_project(forget)
        return 0

    projects = pickable()
    if live_only:
        projects = [p for p in projects if p.live]
    needle = " ".join(query).lower()
    if needle:
        words = needle.split()
        projects = [p for p in projects if all(w in f"{p.label} {p.target}".lower() for w in words)]

    if rows:
        print("\n".join(fzf_rows(projects)))
        return 0
    if list_only:
        print("\n".join(list_lines(projects)))
        return 0 if projects else EXIT_NOTHING
    if not projects:
        print("optmux pick: no projects" + (" match" if needle or live_only else " yet (start optmux in one first)"), file=sys.stderr)
        return EXIT_NOTHING

    if select is not None:
        target = projects[select - 1].target
    elif auto_single and len(projects) == 1:
        target = projects[0].target
    elif shutil.which("fzf") and sys.stdin.isatty():
        target = choose_with_fzf(projects)
    else:
        target = choose_with_menu(projects)
    if target is None:
        return EXIT_CANCELLED

    chosen = next(p for p in projects if p.target == target)
    subprocess.run(launch_command(chosen))  # a child, so we return after detach
    return 0
