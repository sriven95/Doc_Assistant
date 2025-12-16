import java.sql.*;

public class DBConnection{
    public int a;
    public int b;
    public int c;
    
    public DBConnection(){
       String dbURL = "jdbc:mysql://localhost:3306/numbers";
        String username ="root";
        String password ="Sriven@123";
            Connection conn = null;
            Statement stmt = null;
            ResultSet rs = null;
            try {
                conn = DriverManager.getConnection(dbURL, username, password);
                System.out.println("connected to db successfully");
                stmt = conn.createStatement();
                rs = stmt.executeQuery("SELECT * FROM input");
                if (rs.next()) {
                    a=rs.getInt(2);
                }
                if (rs.next()) {
                    b=rs.getInt(2);
                }
                if (rs.next()) {
                    c=rs.getInt(2);
                }
            } catch (SQLException e) {
                System.out.println("Connection failed: " + e.getMessage());
                e.printStackTrace();
            } finally {
                try {
                    if (rs != null) rs.close();
                } catch (SQLException ex) {
                    System.out.println("Failed to close ResultSet: " + ex.getMessage());
                    ex.printStackTrace();
                }
                try {
                    if (stmt != null) stmt.close();
                } catch (SQLException ex) {
                    System.out.println("Failed to close Statement: " + ex.getMessage());
                    ex.printStackTrace();
                }
                try {
                    if (conn != null) conn.close();
                } catch (SQLException ex) {
                    System.out.println("Failed to close Connection: " + ex.getMessage());
                    ex.printStackTrace();
                }
            }
    }
    public static void main(String args[]){
        DBConnection dbConn = new DBConnection();
        System.out.println("Value of a: " + dbConn.a);
        System.out.println("Value of b: " + dbConn.b);
        System.out.println("Value of c: " + dbConn.c);
        
    }
}