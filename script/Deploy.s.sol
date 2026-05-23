// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {AgentRegistry} from "../contracts/AgentRegistry.sol";
import {TaskEscrow} from "../contracts/TaskEscrow.sol";
import {Reputation} from "../contracts/Reputation.sol";
import {TaskMarketplace} from "../contracts/TaskMarketplace.sol";

contract Deploy {
    function run() external returns (AgentRegistry, TaskEscrow, Reputation, TaskMarketplace) {
        return (new AgentRegistry(), new TaskEscrow(), new Reputation(msg.sender), new TaskMarketplace());
    }
}
