
public class Add {
public static void main(String args[]){
    DBConnection dbConn = new DBConnection();
    int a=dbConn.a;
    int b=dbConn.b;
    System.out.println("First number is: "+a);
    System.out.println("Second number is: "+b);
    int sum=a+b;
    System.out.println("The sum of two numbers is: "+sum);


}
}