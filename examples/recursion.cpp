#include <bits/stdc++.h>
using namespace std;

int factorial(int n) {
    int result = 1;
    if (n > 1) {
        result = n * factorial(n - 1);
    }
    return result;
}

int main() {
    int n = 4;
    int result = factorial(n);
    cout << result << endl;
    return 0;
}
