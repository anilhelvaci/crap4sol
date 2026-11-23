// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Vault} from "../src/Vault.sol";

contract VaultTest {
    function test_deposit() public {
        Vault v = new Vault();
        v.deposit(5);
        require(v.total() == 6, "total");
    }

    function test_setClamps() public {
        Vault v = new Vault();
        v.set(5000);
        require(v.total() == 1000, "clamped");
    }
}
