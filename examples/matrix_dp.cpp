#include <bits/stdc++.h>
using namespace std;

int main() {
    int dp[4][5] = {};
    int row = 0;
    int col = 0;
    for (row = 0; row < 4; ++row) {
        for (col = 0; col < 5; ++col) {
            if (row == 0 || col == 0) dp[row][col] = 1;
            else dp[row][col] = dp[row - 1][col] + dp[row][col - 1];
        }
    }
    cout << "paths = " << dp[3][4] << endl;
    return 0;
}
