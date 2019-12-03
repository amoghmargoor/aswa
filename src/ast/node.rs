use std::fmt::{Display, Debug};
use std::any::Any;
use crate::ast::basic_ast::{Select, SelectItem, AliasName};
use crate::ast::expression::Expression;

pub trait NodeTrait: Display + Debug {
    /*fn accept<R, C>(&self, visitor: AstVisitor<R, C>, context: C) -> R
    {
        return visitor.visitNode(this, context);
    }*/

    fn get_children(&self) -> Vec<Node>;
}

pub enum Node {
    Select(Select),
    SelectItem(SelectItem),
    AliasName(AliasName),
    Expression(Expression)
}

impl From<Select> for Node {
    fn from(s: Select) -> Self {
        Node::Select(s)
    }
}

impl From<SelectItem> for Node {
    fn from(s: SelectItem) -> Self {
        Node::SelectItem(s)
    }
}

impl From<AliasName> for Node {
    fn from(a: AliasName) -> Self {
        Node::AliasName(a)
    }
}

impl From<Expression> for Node {
    fn from(e: Expression) -> Self {
        Node::Expression(e)
    }
}