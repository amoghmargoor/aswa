use std::fmt;
use crate::ast::node::{NodeTrait, Node};
use crate::ast::expression::{Expression, BooleanExpression};
use std::any::Any;
use itertools::{Itertools, join};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Query {
    pub with: Option<With>,
    pub body: QueryBody
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QueryBody {
    pub query_term: Select,
    pub order_by: Option<Vec<SortItem>>,
    pub limit: Option<Limit>
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SortItem {
    pub expression: Expression,
    pub sort_order: Option<SortOrder>,
    pub null_order: Option<NullOrder>
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum SortOrder {
    Asc,
    Desc,
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum NullOrder {
    First,
    Last,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct With {
    pub recursive: bool,
    pub body: Vec<NamedQuery>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NamedQuery {
    pub tbl_name: String,
    pub columns: Option<Vec<ColumnName>>,
    pub body: Query
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Select {
    pub distinctness: Option<Distinctness>,
    pub projection: Vec<SelectItem>,
    pub from: String,
    pub filter: Expression,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Limit {
    pub expr: Expression,
    pub offset: Option<Expression>, /* TODO distinction between LIMIT offset, count and LIMIT count
                               * OFFSET offset */
}

impl fmt::Display for Select {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let distinctness = match self.distinctness {
            Some(d) => format!("{}", d),
            _ => String::from("")
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
    pub expression: Expression,
    pub alias: Option<AliasName>
}

impl fmt::Display for SelectItem {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let res = match &self.alias {
            Some(a) => write!(f, "{} as {}", self.expression, a),
            _ => write!(f, "{}", self.expression)
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
    pub identifier: String
}

impl fmt::Display for AliasName {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.identifier)
    }
}

impl NodeTrait for AliasName {

    fn get_children(&self) -> Vec<Node> {
        // FixMe
        return vec!()
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ColumnName {
    pub identifier: String
}

impl fmt::Display for ColumnName {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.identifier)
    }
}

impl NodeTrait for ColumnName {

    fn get_children(&self) -> Vec<Node> {
        // FixMe
        return vec!()
    }
}

