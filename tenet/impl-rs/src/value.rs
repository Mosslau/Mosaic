//! 运行时值系统：解释器中的一等公民。
//!
//! Tenet 是静态类型语言（类型标注存在于源码中），但解释器采用
//! 动态值 + 运行时检查的方式执行，与 Go 代码生成端（编译期类型）
//! 形成互补：解释器验证「语义正确」，代码生成端验证「类型正确」。

use std::fmt;

use crate::ast::{BinaryOp, Type, UnaryOp};
use crate::error::{TenetError, TResult};

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Int(i64),
    Float(f64),
    Bool(bool),
    Str(String),
    /// 空值：无返回值的函数调用的结果。
    Nil,
}

impl Value {
    pub fn type_name(&self) -> &'static str {
        match self {
            Value::Int(_) => "int",
            Value::Float(_) => "float",
            Value::Bool(_) => "bool",
            Value::Str(_) => "string",
            Value::Nil => "nil",
        }
    }

    /// 值在类型系统中的类别（`Nil` 没有对应标注类型）。
    pub fn as_type(&self) -> Option<Type> {
        match self {
            Value::Int(_) => Some(Type::Int),
            Value::Float(_) => Some(Type::Float),
            Value::Bool(_) => Some(Type::Bool),
            Value::Str(_) => Some(Type::Str),
            Value::Nil => None,
        }
    }

    /// 与给定标注类型是否匹配（int 与 float 可互相视为数值）。
    pub fn matches(&self, ty: Type) -> bool {
        match (self, ty) {
            (Value::Int(_), Type::Int) | (Value::Float(_), Type::Float) => true,
            (Value::Bool(_), Type::Bool) => true,
            (Value::Str(_), Type::Str) => true,
            _ => false,
        }
    }

    /// 二元运算。语义规则：
    /// - `+`：int+int→int，float+float→float，int+float→float，string+string→拼接
    /// - `- * /`：数值；int/int 整除，任一为 float 则浮点除
    /// - `%`：仅 int
    /// - 比较：数值互比（int/float 互通），字符串按字典序
    /// - `&& ||`：仅 bool，短路求值由调用方处理
    pub fn apply_binary(&self, op: BinaryOp, rhs: &Value) -> TResult<Value> {
        use Value::*;
        match (self, rhs) {
            // ---- 数值运算 ----
            (Int(a), Int(b)) => match op {
                BinaryOp::Add => Ok(Int(a + b)),
                BinaryOp::Sub => Ok(Int(a - b)),
                BinaryOp::Mul => Ok(Int(a * b)),
                BinaryOp::Div => {
                    if *b == 0 {
                        Err(TenetError::new("整数除以零", None))
                    } else {
                        Ok(Int(a / b))
                    }
                }
                BinaryOp::Mod => {
                    if *b == 0 {
                        Err(TenetError::new("整数取模零", None))
                    } else {
                        Ok(Int(a % b))
                    }
                }
                BinaryOp::Eq => Ok(Bool(a == b)),
                BinaryOp::NotEq => Ok(Bool(a != b)),
                BinaryOp::Lt => Ok(Bool(a < b)),
                BinaryOp::LtEq => Ok(Bool(a <= b)),
                BinaryOp::Gt => Ok(Bool(a > b)),
                BinaryOp::GtEq => Ok(Bool(a >= b)),
                _ => Err(type_err(op, self, rhs)),
            },
            (Int(a), Float(b)) | (Float(b), Int(a)) => {
                // 两种模式的绑定一致：a 为 i64、b 为 f64
                numeric_float(op, *a as f64, *b)
            }
            (Float(a), Float(b)) => numeric_float(op, *a, *b),
            // ---- 字符串 ----
            (Str(a), Str(b)) => match op {
                BinaryOp::Add => Ok(Str(format!("{a}{b}"))),
                BinaryOp::Eq => Ok(Bool(a == b)),
                BinaryOp::NotEq => Ok(Bool(a != b)),
                BinaryOp::Lt => Ok(Bool(a < b)),
                BinaryOp::LtEq => Ok(Bool(a <= b)),
                BinaryOp::Gt => Ok(Bool(a > b)),
                BinaryOp::GtEq => Ok(Bool(a >= b)),
                _ => Err(type_err(op, self, rhs)),
            },
            // ---- 布尔 ----
            (Bool(a), Bool(b)) => match op {
                BinaryOp::Eq => Ok(Bool(a == b)),
                BinaryOp::NotEq => Ok(Bool(a != b)),
                _ => Err(type_err(op, self, rhs)),
            },
            // ---- 其它类型组合 ----
            _ => Err(type_err(op, self, rhs)),
        }
    }

    /// 一元运算：`-` 数值取负，`!` 布尔取反。
    pub fn apply_unary(&self, op: UnaryOp) -> TResult<Value> {
        match (op, self) {
            (UnaryOp::Neg, Value::Int(a)) => Ok(Value::Int(-a)),
            (UnaryOp::Neg, Value::Float(a)) => Ok(Value::Float(-a)),
            (UnaryOp::Not, Value::Bool(a)) => Ok(Value::Bool(!a)),
            _ => Err(TenetError::new(
                format!(
                    "一元运算符 `{}` 不能作用于 {}",
                    match op {
                        UnaryOp::Neg => "-",
                        UnaryOp::Not => "!",
                    },
                    self.type_name()
                ),
                None,
            )),
        }
    }
}

fn numeric_float(op: BinaryOp, a: f64, b: f64) -> TResult<Value> {
    use Value::*;
    match op {
        BinaryOp::Add => Ok(Float(a + b)),
        BinaryOp::Sub => Ok(Float(a - b)),
        BinaryOp::Mul => Ok(Float(a * b)),
        BinaryOp::Div => {
            if b == 0.0 {
                Err(TenetError::new("浮点除以零", None))
            } else {
                Ok(Float(a / b))
            }
        }
        BinaryOp::Eq => Ok(Bool(a == b)),
        BinaryOp::NotEq => Ok(Bool(a != b)),
        BinaryOp::Lt => Ok(Bool(a < b)),
        BinaryOp::LtEq => Ok(Bool(a <= b)),
        BinaryOp::Gt => Ok(Bool(a > b)),
        BinaryOp::GtEq => Ok(Bool(a >= b)),
        _ => Err(TenetError::new(
            format!("运算符 `{}` 不能作用于 float", op_name(op)),
            None,
        )),
    }
}

fn op_name(op: BinaryOp) -> &'static str {
    match op {
        BinaryOp::Add => "+",
        BinaryOp::Sub => "-",
        BinaryOp::Mul => "*",
        BinaryOp::Div => "/",
        BinaryOp::Mod => "%",
        BinaryOp::Eq => "==",
        BinaryOp::NotEq => "!=",
        BinaryOp::Lt => "<",
        BinaryOp::LtEq => "<=",
        BinaryOp::Gt => ">",
        BinaryOp::GtEq => ">=",
        BinaryOp::And => "&&",
        BinaryOp::Or => "||",
    }
}

fn type_err(op: BinaryOp, lhs: &Value, rhs: &Value) -> TenetError {
    TenetError::new(
        format!(
            "运算符 `{}` 不能作用于 {} 和 {}",
            op_name(op),
            lhs.type_name(),
            rhs.type_name()
        ),
        None,
    )
}

impl fmt::Display for Value {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Value::Int(v) => write!(f, "{v}"),
            Value::Float(v) => write!(f, "{v}"),
            Value::Bool(v) => write!(f, "{v}"),
            Value::Str(v) => write!(f, "{v}"),
            Value::Nil => write!(f, "nil"),
        }
    }
}
