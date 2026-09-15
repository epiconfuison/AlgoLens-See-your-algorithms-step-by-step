#include <bits/stdc++.h>
using namespace std;

int main() {
    vector<int> a{7, 3, 9, 1, 5, 2};
    int n = static_cast<int>(a.size());
    int i = 0;
    int j = 0;
    for (i = 0; i < n - 1; ++i) {
        for (j = 0; j < n - i - 1; ++j) {
            if (a[j] > a[j + 1]) {
                int temp = a[j];
                a[j] = a[j + 1];
                a[j + 1] = temp;
            }
        }
    }
    for (int value : a) cout << value << ' ';
    cout << endl;
    return 0;
}
