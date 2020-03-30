use crate::sql_parser::parser::{parseStatement, parseExpression};
#[cfg(test)]

#[test]
fn test_set_operator_query() {
    assertStatement("SELECT a from abc intersect distinct select b from def intersect all select c from ghi");
    assertStatement("SELECT a from abc union distinct select b from def union all select c from ghi");
    assertStatement("SELECT a from abc except select b from def");
}

#[test]
fn testGenericLiteral() {
    assertGenericLiteral("VARCHAR");
    assertGenericLiteral("BIGINT");
    assertGenericLiteral("DOUBLE");
    assertGenericLiteral("BOOLEAN");
    assertGenericLiteral("DATE");
    assertGenericLiteral("foo");
}

#[test]
fn testBinaryLiteral() {
    //assertExpression("x' '");
    //assertExpression("x''");
    assertExpression("X'abcdef1234567890ABCDEF'");
    assertInvalidExpression("X 'a b'");
    assertInvalidExpression("X'a b c'");
    assertInvalidExpression("X'a z'");
}

#[test]
fn testLiterals() {
    assertExpression(("TIME".to_string() + " 'abc'").as_str());
    assertExpression(("TIMESTAMP".to_string() + " 'abc'").as_str());
    assertExpression("INTERVAL '33' day");
    assertExpression("INTERVAL '33' day to second");
    assertExpression("CHAR 'abc'");
}

#[test]
fn testArrayConstructor() {
    assertExpression("ARRAY []");
    assertExpression("ARRAY [1, 2]");
    assertExpression("ARRAY [1e0, 2.5e0]");
    assertExpression("ARRAY ['hi']");
    assertExpression("ARRAY ['hi', 'hello']");
}

#[test]
fn testArraySubscript() {
    assertExpression("ARRAY [1, 2][1]");
    assertInvalidExpression("CASE WHEN TRUE THEN ARRAY[1,2] END[1]");
}

#[test]
fn testDouble() {
    assertExpression("123E7");
    assertExpression("123.E7");
    assertExpression("123.0E7");
    assertExpression("123E+7");
    assertExpression("123E-7");
    assertExpression("123.456E7");
    assertExpression("123.456E+7");
    assertExpression("123.456E-7");
    assertExpression(".4E42");
    assertExpression(".4E+42");
    assertExpression(".4E-42");
}

#[test]
fn testCast() {
    assertCast("foo(42, 55) ARRAY");
    assertCast("varchar");
    assertCast("bigint");
    assertCast("BIGINT");
    assertCast("double");
    assertCast("DOUBLE");
    assertCast("DOUBLE PRECISION");
    assertCast("DOUBLE   PRECISION");
    assertCast("double precision");
    assertCast("boolean");
    assertCast("date");
    assertCast("time");
    assertCast("timestamp");
    assertCast("time with time zone");
    assertCast("timestamp with time zone");
    assertCast("foo");
    assertCast("FOO");

    assertCast("ARRAY<bigint>");
    assertCast("ARRAY<BIGINT>");
    assertCast("array<bigint>");
    assertCast("array < bigint  >");

    assertCast("ARRAY(bigint)");
    assertCast("ARRAY(BIGINT)");
    assertCast("array(bigint)");
    assertCast("array ( bigint  )");

    assertCast("array<array<bigint>>");
    assertCast("array(array(bigint))");

    assertCast("foo ARRAY");
    assertCast("boolean array  array ARRAY");
    assertCast("boolean ARRAY ARRAY ARRAY");
    assertCast("ARRAY<boolean> ARRAY ARRAY");

    assertCast("map(BIGINT,array(VARCHAR))");
    assertCast("map<BIGINT,array<VARCHAR>>");

    assertCast("varchar(42)");
    assertCast("foo(42,55)");
    assertCast("foo(BIGINT,array(VARCHAR))");
    assertCast("ARRAY<varchar(42)>");
    assertCast("ARRAY<foo(42,55)>");
    assertCast("varchar(42) ARRAY");
    assertCast("foo(42, 55) ARRAY");

    assertCast("ROW(m DOUBLE)");
    assertCast("ROW(m DOUBLE)");
    assertCast("ROW(x BIGINT,y DOUBLE)");
    assertCast("ROW(x BIGINT, y DOUBLE)");
    assertCast("ROW(x BIGINT, y DOUBLE, z ROW(m array<bigint>,n map<double,timestamp>))");
    assertCast("array<ROW(x BIGINT, y TIMESTAMP)>");

    assertCast("interval year to month");
}

#[test]
fn testArithmeticUnary() {
    assertExpression("9");
    assertExpression("+9");
    assertExpression("+ 9");
    assertExpression("++9");
    assertExpression("+ +9");
    assertExpression("+ + 9");

    assertExpression("+++9");
    assertExpression("+ + +9");
    assertExpression("+ + + 9");

    assertExpression("-9");
    assertExpression("- 9");

    assertExpression("- + 9");
    assertExpression("-+9");

    assertExpression("+ - + 9");
    assertExpression("+-+9");

    assertExpression("- -9");
    assertExpression("- - 9");

    assertExpression("- + - + 9");
    assertExpression("-+-+9");

    assertExpression("+ - + - + 9");
    assertExpression("+-+-+9");

    assertExpression("- - -9");
    assertExpression("- - - 9");
}

//@Test
//public void testCoalesce()
//{
//assertInvalidExpression("coalesce()", "The 'coalesce' function must have at least two arguments");
//assertInvalidExpression("coalesce(5)", "The 'coalesce' function must have at least two arguments");
//assertExpression("coalesce(13, 42)", new CoalesceExpression(new LongLiteral("13"), new LongLiteral("42")));
//assertExpression("coalesce(6, 7, 8)", new CoalesceExpression(new LongLiteral("6"), new LongLiteral("7"), new LongLiteral("8")));
//assertExpression("coalesce(13, null)", new CoalesceExpression(new LongLiteral("13"), new NullLiteral()));
//assertExpression("coalesce(null, 13)", new CoalesceExpression(new NullLiteral(), new LongLiteral("13")));
//assertExpression("coalesce(null, null)", new CoalesceExpression(new NullLiteral(), new NullLiteral()));
//}
//
//@Test
//public void testDoubleInQuery()
//{
//assertStatement("SELECT 123.456E7 FROM DUAL",
//simpleQuery(
//selectList(new DoubleLiteral("123.456E7")),
//table(QualifiedName.of("DUAL"))));
//}

fn assertGenericLiteral(type_str: &str) {
    assertExpression((type_str.to_string() + " 'abc'").as_ref());
}

fn assertExpression(expression: &str) {
    parseExpression(expression).unwrap();
}

fn assertInvalidExpression(expression: &str) {
    assert!(parseExpression(expression).is_err(),
            "Error is expected while parsing invalid expression ".to_string() + expression)
}

fn assertStatement(sql: &str) {
    parseStatement(sql).unwrap();
}

fn assertInvalidStatement(sql: &str) {
    assert!(parseStatement(sql).is_err(),
            "Error expected while parsing invalid Statement ".to_string() + sql)
}

fn assertCast(type_str: &str)
{
    // assertExpression("CAST(null AS " + type_str + ")");
}
