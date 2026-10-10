# agents package — Unified namespace bridging backend and root
import os
_root_agents = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "agents"))
if os.path.isdir(_root_agents) and _root_agents not in __path__:
    __path__.append(_root_agents)
