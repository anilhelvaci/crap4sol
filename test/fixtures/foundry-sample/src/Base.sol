// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

abstract contract Base {
    function hook() public virtual returns (uint256);

    function baseHelper() public pure returns (uint256) {
        return 7;
    }
}
