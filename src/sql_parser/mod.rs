use lalrpop_util;

#[allow(dead_code)]
lalrpop_mod!(sql, "/sql_parser/sql.rs");

pub mod ast;
pub mod token;
pub mod parser;