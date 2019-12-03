use std::fmt;
use crate::ast::node::{NodeTrait, Node};
use crate::ast::expression::{Expression, BooleanExpression};
use std::any::Any;
use syntax::util::map_in_place::MapInPlace;
use itertools::{Itertools, join};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Select {
    pub distinctness: Option<Distinctness>,
    pub projection: Vec<Box<SelectItem>>,
    pub from: Box<Expression>,
    pub filter: Box<BooleanExpression>,
}

impl fmt::Display for Select {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let distinctness = match self.distinctness {
            Some(d) => format!("{}", d),
            _ => ""
        };
        write!(f, "select {} {} \n from {} \n where {}",
               distinctness, join(&self.projection, ","),
               self.from, self.filter)
    }
}

impl NodeTrait for Select {

    /*fn accept<R, C>(&self, visitor: AstVisitor<R, C>, context: C) -> R
    {
        return visitor.visitSelect(this, context);
    }*/

    fn get_children(&self) -> Vec<Node> {
        // FixME
        return vec!()
    }
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum Distinctness {
    Distinct,
    All
}

impl std::fmt::Display for Distinctness {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            Distinctness::Distinct => write!(f, "distinct"),
            Distinctness::All => write!(f, "all")
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SelectItem {
    expr: Box<Expression>,
    alias: Option<AliasName>
}

impl fmt::Display for SelectItem {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let res = match &self.alias {
            Some(a) => write!(f, "{} as {}", self.expr, a),
            _ => write!(f, "{}", self.expr)
        };
        res
    }
}

impl NodeTrait for SelectItem {

    /*fn accept<R, C>(&self, visitor: AstVisitor<R, C>, context: C) -> R
    {
        return visitor.visitSelect(this, context);
    }*/

    // FixMe
    fn get_children(&self) -> Vec<Node> {
        return vec!()
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AliasName {
    pub identifier: Box<Expression>
}

impl fmt::Display for AliasName {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.identifier);
    }
}

impl NodeTrait for AliasName {

    fn get_children(&self) -> Vec<Node> {
        // FixMe
        return vec!()
    }
}
