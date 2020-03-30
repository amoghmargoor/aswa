use crate::sql_parser::ast::basic_ast::{Query, Statement};
use crate::sql_parser::token::Tokenizer;
use crate::sql_parser::token::Tok;
use super::sql::{ExpressionParser, StatementParser};
use lalrpop_util;
use crate::sql_parser::ast::expression::Expression;

pub type Error<'input> = lalrpop_util::ParseError<usize, crate::sql_parser::token::Tok<'input>, crate::sql_parser::token::Error>;

pub fn parseStatement(input: &str) -> Result<Statement, Error> {
    let tokenizer = Tokenizer::new(input, 0);
    let sql = StatementParser::new().parse(input, tokenizer)?;

    Ok(sql)
}

pub fn parseExpression(input: &str) -> Result<Expression, Error> {
    let tokenizer = Tokenizer::new(input, 0);
    let sql_expression = ExpressionParser::new().parse(input, tokenizer)?;

    Ok(sql_expression)
}
