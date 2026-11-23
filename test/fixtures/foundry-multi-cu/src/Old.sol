// SPDX-License-Identifier: MIT
pragma solidity =0.8.26;

import {clamp} from "./MathLib.sol";

contract Old {
    function o(uint256 v) external pure returns (uint256) {
        return clamp(v, 3);
    }
}
