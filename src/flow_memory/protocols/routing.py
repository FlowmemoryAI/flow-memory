"""Protocol routing helpers."""

from flow_memory.protocols.envelopes import ProtocolEnvelope


def route_for(envelope: ProtocolEnvelope) -> str:
    return envelope.protocol
