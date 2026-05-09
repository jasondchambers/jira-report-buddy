from typing import cast, final, override
from pick import Picker, KEYS_ENTER, Position
from pick.backend import Backend
from pick.blessed_backend import BlessedBackend


def _get_key_codes() -> tuple[int, int, int, int, int]:
    try:
        import curses
        return curses.KEY_UP, curses.KEY_DOWN, curses.KEY_RIGHT, curses.KEY_ENTER, curses.KEY_BACKSPACE
    except ImportError:
        return 259, 258, 261, 343, 263


_KEY_UP, _KEY_DOWN, _KEY_RIGHT, _KEY_ENTER, _KEY_BACKSPACE = _get_key_codes()

_SEQUENCE_MAP: dict[str, int] = {
    'KEY_UP':        _KEY_UP,
    'KEY_DOWN':      _KEY_DOWN,
    'KEY_RIGHT':     _KEY_RIGHT,
    'KEY_ENTER':     _KEY_ENTER,
    'KEY_BACKSPACE': _KEY_BACKSPACE,
    'KEY_DELETE':    _KEY_BACKSPACE,
}


class _BlessedBackend(BlessedBackend):
    @override
    def getch(self) -> int:
        key = self._term.inkey()
        if key.is_sequence:
            return _SEQUENCE_MAP.get(key.name or "", -1)
        return ord(key) if key else -1


@final
class _SearchPicker(Picker[str]):
    _all_options: list[str] = []
    _search_query: str = ""

    @override
    def __post_init__(self) -> None:
        self._all_options = list(self.options)
        self._search_query = ""
        super().__post_init__()

    def _apply_filter(self) -> None:
        query = self._search_query.lower()
        filtered = [o for o in self._all_options if query in o.lower()] if query else self._all_options
        self.options = filtered or self._all_options
        self.index = 0

    @override
    def get_title_lines(self, *, max_width: int = 80) -> list[str]:
        lines = super().get_title_lines(max_width=max_width)
        return lines + [f"Search: {self._search_query}_", ""]

    @override
    def get_selected(self) -> tuple[str, int]:
        opt, _ = cast(tuple[str, int], super().get_selected())  # pyright: ignore[reportUnknownMemberType]
        return opt, self._all_options.index(opt)

    @override
    def run_loop(self, screen: Backend, position: Position) -> tuple[str, int]:
        while True:
            self.draw(screen)
            c = screen.getch()
            if c == _KEY_UP:
                self.move_up()
            elif c == _KEY_DOWN:
                self.move_down()
            elif c in KEYS_ENTER:
                return self.get_selected()
            elif c in (_KEY_BACKSPACE, 127, 8):
                self._search_query = self._search_query[:-1]
                self._apply_filter()
            elif 32 <= c <= 126:
                self._search_query += chr(c)
                self._apply_filter()


def fuzzy_find(options: list[str], title: str | None = None) -> tuple[str, int]:
    picker = _SearchPicker(options, title, backend=_BlessedBackend())
    return cast(tuple[str, int], picker.start())
