from fastapi import APIRouter

router = APIRouter()


@router.get("/online-vehicles")
async def online_vehicles():
    """实时在线车辆数"""
    # TODO: 从 ClickHouse 查询
    return {"online_vehicles": 0, "timestamp": None}


@router.get("/fault-summary")
async def fault_summary():
    """故障汇总"""
    # TODO: 从 ClickHouse 查询
    return {"fault_vehicles": 0, "top_fault_codes": []}


@router.get("/battery-risk")
async def battery_risk():
    """电池风险统计"""
    # TODO: 从 ClickHouse 查询
    return {"high_temp_count": 0, "avg_soc": 0}


@router.get("/vehicle-health/{vehicle_id}")
async def vehicle_health(vehicle_id: str):
    """车辆健康评分"""
    # TODO: 计算健康分
    return {"vehicle_id": vehicle_id, "health_score": 85, "risk_level": "low"}
