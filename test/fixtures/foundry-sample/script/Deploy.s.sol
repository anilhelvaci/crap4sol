// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Vault} from "../src/Vault.sol";

contract Deploy {
    function run() external returns (Vault) {
        return new Vault();
    }
}
