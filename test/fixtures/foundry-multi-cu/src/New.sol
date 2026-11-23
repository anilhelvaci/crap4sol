// SPDX-License-Identifier: MIT
pragma solidity =0.8.39;

import {clamp, Bits} from "./MathLib.sol";

contract New {
    function n(uint256 v) external pure returns (uint256) {
        return clamp(Bits.low(v), 3);
    }
}
