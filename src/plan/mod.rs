// Plan Nodes
trait NodeTrait<C> {
    fn get_children(&self) -> Vec<&C>;
}

pub enum Node {
    LogicalNode(LogicalNode),
    PhysicalNode(PhysicalNode)
}
// Logical Nodes
// Every Logical Node needs to implement `LogicalNodeTrait` and `NodeTrait`
// Currently not sure how to enforce the above condition
// TODO: Enforce the above two traits to be implemented by all Logical Nodes
trait LogicalNodeTrait {
    fn get_schema(&self) -> ();
}

pub enum LogicalNode {
    TableScan(TableScan),
    Filter(Filter),
    Project(Project)
}

pub struct TableScan {
    full_table_name: String
}

impl TableScan {
    fn get_children(&self) -> Vec<&LogicalNode> {
        vec!()
    }
}

pub struct Filter {
    expr: String,
    child: Box<LogicalNode>
}

impl Filter {
    fn get_children(&self) -> Vec<&LogicalNode> {
        vec!(self.child.as_ref())
    }
}

pub struct Project {
    columns: Vec<String>,
    child: Box<LogicalNode>,
}

impl Project {
    fn get_children(&self) -> Vec<&LogicalNode> {
        vec!(self.child.as_ref())
    }
}

impl NodeTrait<LogicalNode> for LogicalNode {
    fn get_children(&self) -> Vec<&LogicalNode> {
        match &self {
            LogicalNode::TableScan(ts) => ts.get_children(),
            LogicalNode::Filter(filter) => filter.get_children(),
            LogicalNode::Project(proj) => proj.get_children()
        }
    }
}

// Physical Nodes
pub enum PhysicalNode {
}

// Visitor
trait LogicalNodeVisitor {
    type Result;
    fn visit_tablescan(&mut self, table_scan: &LogicalNode) -> Self::Result;
    fn visit_filter(&mut self, filter: &LogicalNode) -> Self::Result;
    fn visit_project(&mut self, project: &LogicalNode) -> Self::Result;
}

trait LogicalNodeVisitable {
    fn accept<V: LogicalNodeVisitor>(&mut self, visitor: &V) -> V::Result;
}
