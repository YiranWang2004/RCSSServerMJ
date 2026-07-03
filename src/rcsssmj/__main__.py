import argparse
import logging
import signal
from types import FrameType

from rcsssmj.games.soccer.game_phase import GamePhase
from rcsssmj.games.soccer.server.soccer_server import SoccerSimServer
from rcsssmj.games.soccer.sim.soccer_referee import SoccerReferee
from rcsssmj.games.soccer.sim.soccer_sim import SoccerSimulation
from rcsssmj.games.soccer.soccer_fields import SoccerFieldVersions, create_soccer_field
from rcsssmj.games.soccer.soccer_rules import SoccerRuleBooks, create_soccer_rule_book

# ---------- LOGGING CONFIG ----------
# console handler
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
ch.setLevel(logging.INFO)

# file handler
fh = logging.FileHandler(filename='console.log', mode='w')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
fh.setLevel(logging.DEBUG)

# configure logging
logging.basicConfig(handlers=[ch, fh], level=logging.DEBUG)
# ---------- LOGGING CONFIG ----------


logger = logging.getLogger(__name__)


def soccer_sim() -> None:
    """Main function for running the MuJoCo based Soccer Simulator."""

    # parse arguments
    parser = argparse.ArgumentParser(description='The RoboCup MuJoCo Soccer Simulation Server.')

    rule_books = [str(book.value) for book in SoccerRuleBooks if book != SoccerRuleBooks.UNKNOWN]
    field_versions = [str(version.value) for version in SoccerFieldVersions if version != SoccerFieldVersions.UNKNOWN]
    game_phases = [phase.value for phase in GamePhase]

    # fmt: off
    # server arguments
    parser.add_argument('--host',       help='The server address.',                 default='127.0.0.1', type=str)
    parser.add_argument('--aport',      help='The agent port.',                     default=60000,       type=int)
    parser.add_argument('--mport',      help='The monitor port.',                   default=60001,       type=int)
    parser.add_argument('--sequential', help='Run sequential with agent clients.',  default=False,       action='store_true')
    parser.add_argument('--sync',       help='Run synchronous with agent clients.', default=False,       action='store_true')
    parser.add_argument('--realtime',   help='Run in real-time mode.',              default=True,        action=argparse.BooleanOptionalAction)
    parser.add_argument('--render',     help='Start internal monitor viewer.',      default=True,        action=argparse.BooleanOptionalAction)
    parser.add_argument('--logfile',    help='Log game to a file.',                 default=None,        nargs='?', const='rcssservermj_monitor.log')

    # simulator / game arguments
    parser.add_argument('--field',       help='The soccer field version.',                                                                type=str, choices=field_versions)
    parser.add_argument('--rules',       help='The soccer rule book.',                                default=SoccerRuleBooks.SSIM.value, type=str, choices=rule_books)
    parser.add_argument('--phase',       help='The game phase (0=first  half, 1=second half, etc.).', default=0,                          type=int, choices=game_phases)
    parser.add_argument('--time',        help='The initial play time in seconds.',                                                        type=float)
    parser.add_argument('--score-left',  help='The initial score for the left team.',                 default=0,                          type=int)
    parser.add_argument('--score-right', help='The initial score for the right team.',                default=0,                          type=int)
    # fmt: on

    args = parser.parse_args()

    # simulation parameter
    rule_book = create_soccer_rule_book(args.rules)
    soccer_field = create_soccer_field(rule_book.default_field_version.value if args.field is None else args.field)
    referee = SoccerReferee()
    initial_game_phase = GamePhase.from_value(args.phase)

    # create simulation
    sim = SoccerSimulation(
        field=soccer_field,
        rules=rule_book,
        referee=referee,
        initial_game_phase=initial_game_phase,
        initial_play_time=args.time,
        initial_score=(args.score_left, args.score_right),
    )

    # create server
    server = SoccerSimServer(
        sim=sim,
        host=args.host,
        agent_port=args.aport,
        monitor_port=args.mport,
        sequential_mode=args.sequential,
        sync_mode=args.sync,
        real_time=args.realtime,
        render=args.render,
        log_file=args.logfile,
    )

    # register SIGINT handler
    def signal_handler(sig: int, frame: FrameType | int | signal.Handlers | None) -> None:
        del sig, frame  # signal unused parameter
        logger.debug(' --> HANDLE SIGINT <--')
        server.shutdown()

    signal.signal(signal.SIGINT, signal_handler)

    # run server
    server.run()


if __name__ == '__main__':
    soccer_sim()
