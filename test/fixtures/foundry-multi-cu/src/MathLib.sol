// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

function clamp(uint256 v, uint256 cap) pure returns (uint256 r) {
    if (v > cap) {
        r = cap;
    } else {
        r = v;
    }
}
