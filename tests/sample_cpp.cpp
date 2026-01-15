// Sample C++ program for testing CO (object) and CC (container) tags
#include <iostream>
#include <fstream>
#include <vector>
#include <string>

int main() {
    // Using cout object (for CO tag testing)
    std::cout << "Hello from C++" << std::endl;

    // Using vector container (for CC tag testing)
    std::vector<int> numbers;
    numbers.push_back(1);
    numbers.push_back(2);
    numbers.push_back(3);

    for (int n : numbers) {
        std::cout << n << std::endl;
    }

    // Using ifstream object
    std::ifstream infile("input.txt");
    std::string line;
    while (std::getline(infile, line)) {
        std::cout << line << std::endl;
    }

    return 0;
}
