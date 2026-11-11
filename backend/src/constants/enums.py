from enum import Enum
class Role(str, Enum):
    admin="admin"
    analyst="analyst"
    viewer="viewer"
class RunStatus(str, Enum):
    queued="queued"
    running="running"
    completed="completed"
    failed="failed"
class ReportStatus(str, Enum):
    draft="draft"
    archived="archived"
FEATURES=("salinity","oxygen","turbidity","chlorophyll")
FEATURE_LABELS={"salinity":"盐度 (‰)","oxygen":"溶解氧 (mg/L)","turbidity":"浊度 (NTU)","chlorophyll":"叶绿素 (μg/L)"}
