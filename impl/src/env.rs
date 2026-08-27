//! 环境（Environment）：变量作用域的链式结构。
//!
//! Tenet 的块（`{}`）与函数调用都会创建新的作用域，子作用域通过
//! `parent` 指针访问外层变量——这就是词法作用域（Lexical Scoping）。
//! 函数调用不捕获环境（没有闭包），因此环境可以安全地以 `Rc` 共享。

use std::cell::RefCell;
use std::collections::HashMap;
use std::rc::Rc;

use crate::error::{TenetError, TResult};
use crate::value::Value;

pub struct Env {
    vars: RefCell<HashMap<String, Value>>,
    parent: Option<Rc<Env>>,
}

impl Env {
    /// 创建一个全局环境（无父作用域）。
    pub fn global() -> Rc<Env> {
        Rc::new(Env {
            vars: RefCell::new(HashMap::new()),
            parent: None,
        })
    }

    /// 以 `parent` 为父作用域创建子环境。
    pub fn child(parent: &Rc<Env>) -> Rc<Env> {
        Rc::new(Env {
            vars: RefCell::new(HashMap::new()),
            parent: Some(Rc::clone(parent)),
        })
    }

    /// 定义变量（总是写入当前作用域，允许遮蔽外层同名变量）。
    pub fn define(&self, name: &str, value: Value) {
        self.vars.borrow_mut().insert(name.to_string(), value);
    }

    /// 读取变量，沿作用域链向上查找。
    pub fn get(&self, name: &str) -> TResult<Value> {
        if let Some(v) = self.vars.borrow().get(name) {
            return Ok(v.clone());
        }
        if let Some(parent) = &self.parent {
            return parent.get(name);
        }
        Err(TenetError::new(format!("未定义的变量 `{name}`"), None))
    }

    /// 赋值：沿作用域链找到变量并修改；找不到则报错。
    pub fn assign(&self, name: &str, value: Value) -> TResult<()> {
        if self.vars.borrow().contains_key(name) {
            self.vars.borrow_mut().insert(name.to_string(), value);
            return Ok(());
        }
        if let Some(parent) = &self.parent {
            return parent.assign(name, value);
        }
        Err(TenetError::new(format!("未定义的变量 `{name}`"), None))
    }
}
