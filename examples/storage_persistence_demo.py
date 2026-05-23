from pathlib import Path
from tempfile import TemporaryDirectory

from flow_memory.storage import AgentStore, SQLiteStore

with TemporaryDirectory() as tmp:
    path = Path(tmp) / "flow-memory.db"
    store = SQLiteStore(path)
    agents = AgentStore(store)
    agents.save_profile("agent-1", {"name": "Persistent"})
    reopened = AgentStore(SQLiteStore(path))
    print(reopened.load_profile("agent-1"))
