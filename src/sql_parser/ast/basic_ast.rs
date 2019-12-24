use std::fmt;
use crate::sql_parser::ast::node::{NodeTrait, Node};
use crate::sql_parser::ast::expression::Expression;
use itertools::join;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Statement {
    Query {
        with: Option<With>,
        body: QueryBody
    },
    Use {
        schema: QualifiedName,
    },
    CreateSchema {
        schema: QualifiedName,
        if_not_exists: bool
    },
    AlterSchema {
        from: QualifiedName,
        to: String
    },
    DropSchema {
        schema: QualifiedName,
        if_exists: bool,
        prop: Option<DropProp>
    },
    CreateTableAsSelect {
        table_name: QualifiedName,
        if_not_exists: bool,
        columns: Option<Vec<ColumnName>>,
        query: Box<Statement>
    },
    CreateTable {
        table_name: QualifiedName,
        if_not_exists: bool,
        table_elements: Vec<TableElement>
    },
    DropTable {
        table_name: QualifiedName,
        if_exists: bool
    },
    InsertInto {
        table_name: QualifiedName,
        columns: Option<Vec<ColumnName>>,
        query: Box<Statement>
    },
    Delete {
        from: QualifiedName,
        filter: Option<Expression>
    },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TableElement {
    ColumnDefinition(String, Box<Type>)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Type {
    Array(Box<Type>),
    Map(Box<Type>, Box<Type>),
    Row(Vec<TableElement>),
    TIME_WITH_TIME_ZONE(Option<Vec<TypeParameter>>),
    TIMESTAMP_WITH_TIME_ZONE(Option<Vec<TypeParameter>>),
    DOUBLE_PRECISION(Option<Vec<TypeParameter>>),
    User_Defined(String, Option<Vec<TypeParameter>>)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TypeParameter {
    IntegerTypeParam(String),
    TypeParam(Type)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum DropProp {
    CASCADE,
    RESTRICT
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QualifiedName {
    pub name: Vec<String>
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Query {
    pub with: Option<With>,
    pub body: QueryBody
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QueryBody {
    pub query_term: QueryTerm,
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
    pub body: Box<Statement>
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Select {
    pub distinctness: Option<Distinctness>,
    pub projection: Vec<SelectItem>,
    pub from: String,
    pub filter: Option<Expression>,
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
        let res = match &self.filter {
            Some(filter) => write!(f, "select {} {} \n from {} where {}",
                                   distinctness, join(&self.projection, ","),
                                   self.from, filter),
            _ => write!(f, "select {} {} \n from {}",
                        distinctness, join(&self.projection, ","),
                        self.from)
        };
        return res
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

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QueryTerm {
    pub select: Select,
    pub other: Option<SetQueryTerm>
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SetQueryTerm {
    pub operator: SetOperator,
    pub query: Box<QueryTerm>
}

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum SetOperator {
    Union,
    Intersect,
    Except
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

