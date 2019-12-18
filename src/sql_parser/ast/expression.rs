use std::fmt;
use std::fmt::Debug;
use crate::sql_parser::ast::node::{Node, NodeTrait};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Expression {
    BooleanExpr(BooleanExpression),
    Identifier {
        name: String
    },
    Literal(Literal)
}

impl From<BooleanExpression> for Expression {
    fn from(original: BooleanExpression) -> Expression {
        Expression::BooleanExpr(original)
    }
}

impl fmt::Display for Expression {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            Expression::BooleanExpr(b) => write!(f, "{}", b),
            Expression::Identifier {
                name
            } => write!(f, "{}", name),
            _ => write!(f, "unsupported")
        }
    }
}

impl NodeTrait for Expression {

    fn get_children(&self) -> Vec<Node> {
        match self {
            Expression::BooleanExpr(_) => vec!(),
            Expression::Identifier {
                name
            } => vec!(),
            _ => vec!()
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BooleanExpression {
    BinaryExpression {
        lhs: Box<Expression>,
        operator: BinaryOperator,
        rhs: Box<Expression>
    },
    UnaryExpression {
        operator: UnaryOperator,
        operand: Box<Expression>
    }
}

impl BooleanExpression {
    pub fn or(lhs: Expression, rhs: Expression) -> Expression {
        BooleanExpression::BinaryExpression {
            lhs: Box::new(lhs),
            operator: BinaryOperator::Or,
            rhs: Box::new(rhs)
        }.into()
    }

    pub fn and(lhs: Expression, rhs: Expression) -> Expression {
        BooleanExpression::BinaryExpression  {
            lhs: Box::new(lhs),
            operator: BinaryOperator::And,
            rhs: Box::new(rhs)
        }.into()
    }

    pub fn not(operand: Expression) -> Expression {
        BooleanExpression::UnaryExpression {
            operator: UnaryOperator::Not,
            operand: Box::new(operand)
        }.into()
    }
}

impl fmt::Display for BooleanExpression {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            BooleanExpression::BinaryExpression {
                lhs, operator, rhs
            } => write!(f, "{} {} {}", lhs, operator, rhs),
            BooleanExpression::UnaryExpression {
                operator, operand
            } => write!(f, "{} {}", operator, operand),
        }
    }
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum BinaryOperator {
    Add,
    And,
    BitwiseAnd,
    BitwiseOr,
    Concat, // String concatenation (||)
    Equals, // = or ==
    Divide,
    Greater,
    GreaterEquals,
    Is,
    IsNot,
    LeftShift,
    Less,
    LessEquals,
    Multiply,
    Modulus,
    NotEquals, // != or <>
    Or,
    RightShift,
    Substract,
}

impl fmt::Display for BinaryOperator {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let s = match self {
            BinaryOperator::Add=> "+",
            BinaryOperator::And=> "and",
            BinaryOperator::BitwiseAnd=> "&",
            BinaryOperator::BitwiseOr=> "|",
            BinaryOperator::Concat=> "||", // String concatenation (||)
            BinaryOperator::Equals=> "=", // = or ==
            BinaryOperator::Divide=> "/",
            BinaryOperator::Greater=> ">",
            BinaryOperator::GreaterEquals=> ">=",
            BinaryOperator::Is=> "is",
            BinaryOperator::IsNot=> "is not",
            BinaryOperator::LeftShift=> "<<",
            BinaryOperator::Less=> "<",
            BinaryOperator::LessEquals=> "<=",
            BinaryOperator::Multiply=> "*",
            BinaryOperator::Modulus=> "%",
            BinaryOperator::NotEquals=> "!=", // != or <>
            BinaryOperator::Or=> "or",
            BinaryOperator::RightShift=> ">>",
            BinaryOperator::Substract=> "-",
        };
        write!(f, "{}", s)
    }
}


#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum UnaryOperator {
    // bitwise negation (~)
    BitwiseNot,
    // negative-sign
    Negative,
    // "NOT"
    Not,
    // positive-sign
    Positive,
}

impl fmt::Display for UnaryOperator {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let s = match self {
            // bitwise negation (~)
            UnaryOperator::BitwiseNot => "~",
            // negative-sign
            UnaryOperator::Negative => "-",
            // "NOT"
            UnaryOperator::Not => "!",
            // positive-sign
            UnaryOperator::Positive => "+"
        };
        write!(f, "{}", s)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Literal {
    Numeric(String),
    String(String),
    Blob(String),
    Null,
    CurrentTime,
    CurrentDate,
    CurrentTimestamp,
}
