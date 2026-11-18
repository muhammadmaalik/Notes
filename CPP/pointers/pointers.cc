#include<iostream>


// consider a normal variable char x {}; char uses 1 byte --(1 byte = 8 bits) of memory. When the
// code is generated a piece of memory will be used from the RAM for this object. Let's say X is assigned to memory address 140, well, 
// whenever we use x in a statement, the program will goto memoery address 140 to access the value stored there.

// The nice thing about variables is that we dont need to worry about teh memoery address assigned, or how many butes are reqquired to store the value of the object.

// Everything is handled by the compiler. It takes care of all the addressing. 
//

//int main(){

//	char x {};
//	char& ref{ x };

//return 0;

//}


// In this simple code, whenever we use ref, the program will goto memoery address 140 and use taht value, again the compilor is going to take care of the addresses and stuff


//int main(){

//	int x{ 5 };
//	std::cout << x << '\n';
//	std::cout << &x << '\n';

//return 0;

//}

// In this above example, we used the address of operator to retrieve the address to variable x, and print that address to the console.

// They are typically printed in hexadecimal values, since humans can't read that long binary values, hex is compact and turns a 32 bit
// number to 8 digits


// The most important thing we can do with an address is access the value stored at that address. The dereference operator retursna  value at a given memory
// at a gviven memory address as an Ivalue

//

//int main(){

//	int x{ 5 };
//	std::cout << x << '\n';
//	std::cout << &x << '\n';
//	std::cout << *(&x) << '\n';

//return 0;
//}


// The Program is quite simple, you assign an integer to a variable, you get the address where that integer is stored and then you attain
// the value stored in that address, which was ofcourse already printed before.

// Now, finally, POINTERS!!!!!, pointers are objects that hold memory address, of another variable, this allows us to store the address
// of some other object to use later on.


// The type that specifies a pointer is a pointer type, for example, int; which is a normal int, int&, an lvalue reference to an int value;
// int* a pointer to an int value


// To create a pointer variable:

//int main(){
//	int x { 5 };
//	int& ref { x };
//	int* ptr;

//return 0;
//}



// A pointer that that has not been initialized is a garbage or a wild pointer like

//int* ptr; -- this is garbage
// int* ptr2{} -- null pointer
//int* ptr3{ &x }


//int main(){

//	int x{ 5 };
//	std::cout << &x << '\n';
//	std::cout << x << '\n';
//	int* ptr{ &x };
//	std::cout << *ptr << '\n';


//return 0;
//}

int main(){
	int x = 5;
	int* ptr =  &x;

	
	std::cout << *ptr << '\n';

	int y = 10;
	ptr = &y;

	std::cout << *ptr << '\n';
 
return 0;
}


////////   HAVE TO CONTINUE THE HEADING NAMED -- SIZE OF POINTERS,, NOT DONE YET --- WILL LEARN THAT CONCEPT SOON !!!!!!!!!!!!
