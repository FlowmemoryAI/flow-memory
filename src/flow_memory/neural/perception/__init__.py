"""Neural perception prototypes."""

from flow_memory.neural.perception.appearance_free import AppearanceFreeTransform
from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
from flow_memory.neural.perception.dorsal import TinyDorsalMotionEncoder
from flow_memory.neural.perception.foveation import FoveatedVideoProcessor
from flow_memory.neural.perception.ventral import TinyVentralEncoder

__all__ = ["AppearanceFreeTransform", "FoveatedVideoProcessor", "TinyDorsalMotionEncoder", "TinyDualStreamEncoder", "TinyVentralEncoder"]
