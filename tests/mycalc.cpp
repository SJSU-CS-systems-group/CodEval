// CLI calculator - C++ implementation
// Based on cli-calc assignment (Downloads/assignments/cli-calc/cli_calc.codeval),
// adapted for C++ with a Makefile build.
//
// Usage: ./mycalc number [+|- number]...

#include <iostream>
#include <cstdlib>
#include <cstring>
#include <cerrno>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "USAGE: " << argv[0] << " number [+|- number]..." << std::endl;
        return 1;
    }

    char* endptr;
    errno = 0;
    long result = strtol(argv[1], &endptr, 10);
    if (*endptr != '\0' || errno != 0) {
        std::cout << "expected an integer. got " << argv[1] << std::endl;
        return 2;
    }

    int i = 2;
    while (i < argc) {
        if (strcmp(argv[i], "+") != 0 && strcmp(argv[i], "-") != 0) {
            std::cout << "expected + or -. got " << argv[i] << std::endl;
            return 2;
        }
        char op = argv[i][0];
        i++;

        if (i >= argc) {
            std::cout << "expected an integer. got " << argv[i - 1] << std::endl;
            return 2;
        }

        errno = 0;
        long num = strtol(argv[i], &endptr, 10);
        if (*endptr != '\0' || errno != 0) {
            std::cout << "expected an integer. got " << argv[i] << std::endl;
            return 2;
        }

        if (op == '+') result += num;
        else result -= num;
        i++;
    }

    std::cout << result << std::endl;
    return 0;
}
