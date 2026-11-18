# core/engine.py
from dataclasses import dataclass
from typing import List, Optional, Set, Union
import unicodedata
from core.loader import LanguagePack


@dataclass(frozen=True)
class KeyEvent:
  char: str = ""  # Ký tự in được do OS tạo ra (ví dụ 'a', 'A', ':')
  is_upper: bool = False  # True nếu chữ cái đầu ra là hoa (Shift hoặc Caps Lock)
  has_modifier: bool = False  # True nếu kèm Ctrl, Alt, Super
  is_break_key: bool = (
      False  # True nếu là Space, Enter, Tab, Esc, Arrow, Backspace...
  )


@dataclass(frozen=True)
class ResetEvent:
  """Sự kiện đổi focus, click chuột hoặc đổi cửa sổ."""

  pass


@dataclass(frozen=True)
class Passthrough:
  pass


@dataclass(frozen=True)
class Replace:
  delete_count: int
  text: str
  consume_key: bool = True


Action = Union[Passthrough, Replace]


@dataclass
class _BufferItem:
  char: str
  is_upper: bool


@dataclass
class _LastTransform:
  trigger_lower: str  # Chuỗi trigger chữ thường đã khớp (vd: "ae")
  raw_items: List[_BufferItem]  # Các phím thô người dùng thực sự đã gõ
  output_text: str  # Chuỗi đầu ra đã chèn (vd: "ä" hoặc "Ä")


class FastTypeEngine:

  def __init__(self, pack: Optional[LanguagePack] = None):
    self._pack: Optional[LanguagePack] = pack
    self._buffer: List[_BufferItem] = []
    self._last_transform: Optional[_LastTransform] = None
    self._locked_triggers: Set[str] = set()

  @property
  def active_pack(self) -> Optional[LanguagePack]:
    return self._pack

  def set_pack(self, pack: Optional[LanguagePack]) -> None:
    """Đổi gói ngôn ngữ hoặc tắt về bộ gõ mặc định (pack=None)."""
    self._pack = pack
    self.reset()

  def reset(self) -> Action:
    """Xóa bộ đệm, last_transform và tập quy tắc bị khóa."""
    self._buffer.clear()
    self._last_transform = None
    self._locked_triggers.clear()
    return Passthrough()

  def process_event(self, event: Union[KeyEvent, ResetEvent]) -> Action:
    if isinstance(event, ResetEvent):
      return self.reset()

    # Khi không có gói nào bật: mọi phím đều passthrough
    if self._pack is None:
      return Passthrough()

    # 1. Phím kèm Ctrl/Alt/Super -> xóa bộ đệm và last_transform, passthrough
    if event.has_modifier:
      self._buffer.clear()
      self._last_transform = None
      return Passthrough()

    # 2. Phím ngắt -> xóa bộ đệm, last_transform và tập quy tắc bị khóa, passthrough
    if event.is_break_key or not event.char:
      return self.reset()

    # 3. Ký tự in được
    ch = event.char
    ch_lower = ch.lower()

    # 3.1. Kiểm tra Hoàn tác (Revert - FR-15)
    if self._last_transform is not None:
      last_trig = self._last_transform.trigger_lower
      if ch_lower == last_trig[-1]:
        delete_len = len(self._last_transform.output_text)
        raw_str = "".join(item.char for item in self._last_transform.raw_items)
        # Khóa quy tắc đó cho đến khi bộ đệm bị xóa
        self._locked_triggers.add(last_trig)
        # Đặt lại bộ đệm bằng chuỗi phím thô
        self._buffer = list(self._last_transform.raw_items)
        self._last_transform = None
        self._trim_buffer()
        return Replace(delete_count=delete_len, text=raw_str, consume_key=True)

    # 3.2. Thêm phím vào bộ đệm & Tìm quy tắc khớp hậu tố
    self._buffer.append(_BufferItem(char=ch, is_upper=event.is_upper))
    self._trim_buffer()

    buf_lower = "".join(item.char.lower() for item in self._buffer)
    matched_trig: Optional[str] = None

    # Nếu nhiều quy tắc cùng khớp hậu tố tại thời điểm này, chọn trigger dài nhất
    for length in range(len(buf_lower), 0, -1):
      candidate = buf_lower[-length:]
      if (
          candidate in self._pack.trigger_map
          and candidate not in self._locked_triggers
      ):
        matched_trig = candidate
        break

    if matched_trig is not None:
      trig_len = len(matched_trig)
      raw_slice = self._buffer[-trig_len:]
      base_output = self._pack.trigger_map[matched_trig]
      final_output = self._apply_case(base_output, raw_slice)

      self._last_transform = _LastTransform(
          trigger_lower=matched_trig,
          raw_items=raw_slice,
          output_text=final_output,
      )
      self._buffer.clear()
      return Replace(
          delete_count=trig_len - 1, text=final_output, consume_key=True
      )

    # 3.3. Không khớp: passthrough, xóa last_transform
    self._last_transform = None
    return Passthrough()

  def _trim_buffer(self) -> None:
    if self._pack and self._pack.max_trigger_len > 0:
      max_len = self._pack.max_trigger_len
      if len(self._buffer) > max_len:
        self._buffer = self._buffer[-max_len:]

  def _apply_case(
      self, base_output: str, raw_slice: List[_BufferItem]
  ) -> str:
    """FR-08 & D-10: Đầu ra viết hoa nếu phím chữ cái đầu tiên của trigger là chữ hoa."""
    first_alpha: Optional[_BufferItem] = None
    for item in raw_slice:
      if item.char.isalpha():
        first_alpha = item
        break

    if first_alpha is not None and first_alpha.is_upper:
      if self._pack and base_output in self._pack.upper_map:
        return self._pack.upper_map[base_output]
      return unicodedata.normalize("NFC", base_output.upper())

    return base_output