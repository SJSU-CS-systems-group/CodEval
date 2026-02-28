// Sample C++ program for CF/NCF objdump-based function detection testing.
// greet() is defined and called; forbidden_func is never present.
#include <iostream>

void greet() {
    std::cout << "Hello World" << std::endl;
}

int main() {
    greet();
    return 0;
}
