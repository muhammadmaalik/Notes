//#include <iostream>

//int main()
//{
//	short value{ 7 }; // &value = 0012FF60
//	short otherValue{ 3 }; // &otherValue = 0012FF54

//	short* ptr{ &value };

//	std::cout << &value << '\n';
//	std::cout << value << '\n';
//	std::cout << ptr << '\n';
//	std::cout << *ptr << '\n';
//	std::cout << '\n';

//	*ptr = 9;

//	std::cout << &value << '\n';
//	std::cout << value << '\n';
//	std::cout << ptr << '\n';
//	std::cout << *ptr << '\n';
//	std::cout << '\n';
//
//	ptr = &otherValue;
//
//	std::cout << &otherValue << '\n';
//	std::cout << otherValue << '\n';
//	std::cout << ptr << '\n';
//	std::cout << *ptr << '\n';
//	std::cout << '\n';

//	std::cout << sizeof(ptr) << '\n';
//	std::cout << sizeof(*ptr) << '\n';

//	return 0;
//}


#include<iostream>

int main(){

	int v1 = 45;
	int* ptr = &v1;

	int v2 = 20;

	ptr = &v2;

	std::cout << v1 << '\n' << v2 << std::endl;

return 0;
}
