// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IVault} from "./IVault.sol";
import {Base} from "./Base.sol";
import {clamp} from "./MathLib.sol";

contract Vault is IVault, Base {
    uint256 public constant CAP = 1000;
    uint256 public total = 1;
    address public owner;

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    fallback() external payable {}

    function deposit(uint256 amount) external {
        total += amount;
    }

    function classify(uint256 x) external pure returns (uint256 r) {
        if (x > 100) {
            r = 3;
        } else if (x > 10) {
            r = 2;
        } else {
            r = 1;
        }
        for (uint256 i = 0; i < x; i++) {
            if (i % 2 == 0) {
                r += 1;
            } else {
                r += 2;
            }
        }
    }

    function set(uint256 v) external onlyOwner {
        total = clamp(v, CAP);
    }

    function set(uint256 v, uint256 cap) external onlyOwner {
        total = clamp(v, cap);
    }

    function hook() public view override returns (uint256) {
        return total;
    }
}
