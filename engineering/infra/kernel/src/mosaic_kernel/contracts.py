"""契约校验与 JSON Schema 生成（D1 契约内核的最小实现）。

设计取舍：
- 只依赖标准库，保证 D0/D1 在没有 pip 安装的环境里也能跑；
- 契约用声明式 spec 描述，校验与 Schema 生成共用同一份 spec，避免两处漂移；
- 校验只做「结构层」：必填、类型、枚举、时间格式、数组元素类型；
  语义校验（口径、权限、血缘完整性）留给各平台的领域模块。
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def canonical_digest(payload: Any) -> str:
    """稳定摘要：契约事件、账本、素材对账都用它，避免 dict 顺序导致漂移。"""
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _type_ok(type_name: str, value: Any) -> bool:
    check = _TYPE_CHECKS.get(type_name)
    return bool(check and check(value))


class ContractSet:
    """一组命名契约：校验 + 导出 JSON Schema。"""

    def __init__(self, name: str, specs: Dict[str, Dict[str, Any]]):
        self.name = name
        self.specs = specs

    def names(self) -> List[str]:
        return sorted(self.specs)

    def validate(self, contract: str, payload: Any) -> List[str]:
        spec = self.specs.get(contract)
        if spec is None:
            return ["unknown contract: %s" % contract]
        if not isinstance(payload, dict):
            return ["payload must be an object"]

        errors: List[str] = []
        for field in spec.get("required", []):
            if field not in payload:
                errors.append("missing required field: %s" % field)

        for field, rule in spec.get("properties", {}).items():
            if field not in payload:
                continue
            value = payload[field]
            declared = rule.get("type")
            types = [declared] if isinstance(declared, str) else list(declared or [])
            if types and not any(_type_ok(t, value) for t in types):
                errors.append(
                    "%s: expected %s, got %s" % (field, "/".join(types), type(value).__name__)
                )
                continue
            if "enum" in rule and value not in rule["enum"]:
                errors.append("%s: %r not in %r" % (field, value, rule["enum"]))
            if rule.get("format") == "date-time" and isinstance(value, str):
                if not _DATETIME_RE.match(value):
                    errors.append("%s: not an ISO-8601 date-time" % field)
            if rule.get("min_length") is not None and isinstance(value, str):
                if len(value) < rule["min_length"]:
                    errors.append("%s: shorter than %d" % (field, rule["min_length"]))
            if rule.get("items") and isinstance(value, list):
                item_rule = rule["items"]
                item_types = item_rule.get("type")
                item_types = [item_types] if isinstance(item_types, str) else list(item_types or [])
                for index, item in enumerate(value):
                    if item_types and not any(_type_ok(t, item) for t in item_types):
                        errors.append(
                            "%s[%d]: expected %s, got %s"
                            % (field, index, "/".join(item_types), type(item).__name__)
                        )
        return errors

    def schema(self, contract: str) -> Dict[str, Any]:
        spec = self.specs[contract]
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": contract,
            "type": "object",
            "required": list(spec.get("required", [])),
            "properties": spec.get("properties", {}),
            "additionalProperties": False,
        }

    def schemas(self) -> Dict[str, Dict[str, Any]]:
        return {name: self.schema(name) for name in self.names()}

    def describe(self) -> Dict[str, Any]:
        return {
            "contract_set": self.name,
            "contracts": self.names(),
            "schemas": self.schemas(),
        }


def require(condition: bool, message: str) -> None:
    """测试与示例里用的小断言，失败即 ValueError。"""
    if not condition:
        raise ValueError(message)


def validate_or_raise(contracts: ContractSet, contract: str, payload: Any) -> None:
    errors = contracts.validate(contract, payload)
    if errors:
        raise ValueError("%s: %s" % (contract, "; ".join(errors)))
