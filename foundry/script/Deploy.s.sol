// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import "../../contracts/AgentRegistry.sol";
import "../../contracts/TaskEscrow.sol";
import "../../contracts/ReputationSBT.sol";
import "../../contracts/TaskMarketplace.sol";

contract DeployFlowMemory {
    AgentRegistry public registry;
    TaskEscrow public escrow;
    ReputationSBT public reputation;
    TaskMarketplace public marketplace;

    function run() external {
        registry = new AgentRegistry();
        escrow = new TaskEscrow();
        reputation = new ReputationSBT();
        marketplace = new TaskMarketplace();
    }
}
