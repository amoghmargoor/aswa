use crate::sql_parser::parser::parse;
#[cfg(test)]

#[test]
fn test_select() {
    //parse("SELECT 1").unwrap();
    //parse("SELECT 1, 'test'").unwrap();

//    parse("SELECT * FROM test WHERE 1").unwrap();
//    parse("SELECT * FROM test WHERE 1 GROUP BY id HAVING count(*) > 1").unwrap();
//    parse("SELECT * FROM test ORDER BY 1").unwrap();
//    parse("SELECT * FROM test ORDER BY 1, id").unwrap();
//    parse("SELECT * FROM test LIMIT 1").unwrap();
    parse("SELECT a from foo").unwrap();

    assert!(
        parse("SELECT 1 FROM WHERE 1").is_err(),
        "error expected when no table name is specified"
    );
}

#[test]
fn test_set_operator_query() {
    parse("SELECT a from abc intersect select b from def").unwrap();
    parse("SELECT a from abc intersect select b from def intersect select c from ghi").unwrap();
    parse("SELECT a from abc union select b from def").unwrap();
    parse("SELECT a from abc except select b from def").unwrap();
}