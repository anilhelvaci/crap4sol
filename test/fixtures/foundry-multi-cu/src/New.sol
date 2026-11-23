// SPDX-License-Identifier: MIT
pragma solidity =0.8.39;

import {clamp} from "./MathLib.sol";

contract New {
    function n(uint256 v) external pure returns (uint256) {
        return clamp(v, 3);
    }
}
