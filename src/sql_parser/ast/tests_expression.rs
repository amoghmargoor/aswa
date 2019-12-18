#[cfg(test)]

use super::expression::*;
use super::expression::Expression;
use super::expression::BinaryOperator;
use super::expression::BooleanExpression;
use crate::sql_parser::ast::expression::BooleanExpression::BinaryExpression;


fn binary_expression_display(op: BinaryOperator, fmt_string: &str) {
    let id1 = Expression::Identifier {
        name: "a".to_string()
    };
    let id2 = Expression::Identifier {
        name: "b".to_string()
    };
    let binary_expression: Expression = BooleanExpression::BinaryExpression {
        lhs: Box::new(id1),
        operator: op,
        rhs: Box::new(id2)
    }.into();
    assert_eq!(format!("{}", binary_expression).as_str(), fmt_string);
}

#[test]
fn test_binary_expression_display() {
    binary_expression_display(BinaryOperator::Greater, "a > b");
    binary_expression_display(BinaryOperator::Less, "a < b");
    binary_expression_display(BinaryOperator::And, "a and b");
    binary_expression_display(BinaryOperator::Or, "a or b");
    binary_expression_display(BinaryOperator::Is, "a is b");
    binary_expression_display(BinaryOperator::IsNot, "a is not b");
    binary_expression_display(BinaryOperator::LessEquals, "a <= b");
    binary_expression_display(BinaryOperator::GreaterEquals, "a >= b");
    binary_expression_display(BinaryOperator::NotEquals, "a != b");
}

#[test]
fn test_simple_binary_expression_comparision() {
    let id1_1 = Expression::Identifier {
        name: "a".to_string()
    };
    let id2_1 = Expression::Identifier {
        name: "b".to_string()
    };
    let id1_2 = id1_1.clone();
    let id2_2 = id2_1.clone();
    let id1_3 = id1_1.clone();
    let id2_3 = id2_1.clone();
    let binary_expression_1: Expression = BooleanExpression::BinaryExpression {
        lhs: Box::new(id1_1),
        operator: BinaryOperator::Greater,
        rhs: Box::new(id2_1)
    }.into();

    let binary_expression_2: Expression = BooleanExpression::BinaryExpression {
        lhs: Box::new(id1_2),
        operator: BinaryOperator::Greater,
        rhs: Box::new(id2_2)
    }.into();

    let binary_expression_3: Expression = BooleanExpression::BinaryExpression {
        lhs: Box::new(id1_3),
        operator: BinaryOperator::Less,
        rhs: Box::new(id2_3)
    }.into();

    let binary_expression_3_clone1 = binary_expression_3.clone();
    let binary_expression_3_clone2 = binary_expression_3.clone();
    let binary_expression_3_clone3 = binary_expression_3.clone();

    let binary_expression_2_clone1 = binary_expression_2.clone();

    let binary_expression_1_clone1 = binary_expression_1.clone();
    let binary_expression_1_clone2 = binary_expression_1.clone();

    let binary_expression_4: Expression = BooleanExpression::BinaryExpression {
        lhs: Box::new(binary_expression_3_clone1),
        operator: BinaryOperator::Or,
        rhs: Box::new(binary_expression_2_clone1)
    }.into();

    let binary_expression_5: Expression = BooleanExpression::BinaryExpression {
        lhs: Box::new(binary_expression_3_clone2),
        operator: BinaryOperator::Or,
        rhs: Box::new(binary_expression_1_clone1)
    }.into();

    let binary_expression_6: Expression = BooleanExpression::BinaryExpression {
        lhs: Box::new(binary_expression_3_clone3),
        operator: BinaryOperator::And,
        rhs: Box::new(binary_expression_1_clone2)
    }.into();

    assert_eq!(binary_expression_1, binary_expression_2);
    assert_ne!(binary_expression_1, binary_expression_3);
    assert_eq!(binary_expression_4, binary_expression_5);
    assert_ne!(binary_expression_4, binary_expression_6);
}
