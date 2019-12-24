use crate::sql_parser::ast::basic_ast::{Query, Statement};
use crate::sql_parser::token::Tokenizer;
use crate::sql_parser::token::Tok;
use super::sql::StatementParser;
use lalrpop_util;

pub type Error<'input> = lalrpop_util::ParseError<usize, crate::sql_parser::token::Tok<'input>, crate::sql_parser::token::Error>;

pub fn parse(input: &str) -> Result<Statement, Error> {
    let tokenizer = Tokenizer::new(input, 0);
    let sql = StatementParser::new().parse(input, tokenizer)?;

    Ok(sql)
}
