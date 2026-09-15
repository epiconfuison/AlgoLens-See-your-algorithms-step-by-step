#include <bits/stdc++.h>
using namespace std;

int main() {
    int a[8] = {1, 3, 5, 7, 9, 11, 13, 15};
    int target = 11;
    int left = 0;
    int right = 7;
    int mid = 0;
    int found = -1;
    while (left <= right) {
        mid = left + (right - left) / 2;
        if (a[mid] == target) {
            found = mid;
            break;
        }
        if (a[mid] < target) left = mid + 1;
        else right = mid - 1;
    }
    cout << "index = " << found << endl;
    return 0;
}
