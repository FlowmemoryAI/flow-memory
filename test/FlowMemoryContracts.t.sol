// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import "../contracts/AgentRegistry.sol";
import "../contracts/Reputation.sol";
import "../contracts/TaskEscrow.sol";
import "../contracts/TaskMarketplace.sol";

contract FlowMemoryContractsTest {
    function testAgentRegistryRegistersAndUpdatesManifest() external {
        AgentRegistry registry = new AgentRegistry();
        bytes32 firstHash = keccak256("manifest:v1");
        bytes32 agentId = registry.registerAgent("did:key:agent", firstHash, "ipfs://manifest-v1");

        AgentRegistry.AgentRecord memory record = registry.getAgent(agentId);
        assert(record.controller == address(this));
        assert(record.manifestHash == firstHash);
        assert(record.active);

        bytes32 secondHash = keccak256("manifest:v2");
        registry.updateManifest(agentId, secondHash, "ipfs://manifest-v2", false);
        AgentRegistry.AgentRecord memory updated = registry.getAgent(agentId);
        assert(updated.manifestHash == secondHash);
        assert(!updated.active);
    }

    function testTaskMarketplaceAssignsAndCloses() external {
        TaskMarketplace marketplace = new TaskMarketplace();
        uint256 taskId = marketplace.postTask(10 ether, keccak256("task-spec"));
        uint256 bidIndex = marketplace.postBid(taskId, 7 ether, keccak256("bid-terms"));

        marketplace.assign(taskId, bidIndex);
        (
            address requester,
            address assignee,
            ,
            ,
            TaskMarketplace.Status assignedStatus
        ) = marketplace.tasks(taskId);
        assert(requester == address(this));
        assert(assignee == address(this));
        assert(uint256(assignedStatus) == uint256(TaskMarketplace.Status.Assigned));

        marketplace.close(taskId);
        (, , , , TaskMarketplace.Status closedStatus) = marketplace.tasks(taskId);
        assert(uint256(closedStatus) == uint256(TaskMarketplace.Status.Closed));
    }

    function testTaskEscrowLifecycleCreditsWithdrawableReward() external {
        TaskEscrow escrow = new TaskEscrow();
        address agent = address(0xBEEF);
        uint256 taskId = escrow.createTask{value: 1 ether}(keccak256("task-spec"));

        escrow.assign(taskId, agent);
        escrow.settle(taskId, keccak256("result"));

        (, address taskAgent, , TaskEscrow.Status status, , ) = escrow.tasks(taskId);
        assert(taskAgent == agent);
        assert(uint256(status) == uint256(TaskEscrow.Status.Settled));
        assert(escrow.withdrawable(agent) == 1 ether);
    }

    function testReputationRecordsPositiveAndNegativeEvents() external {
        Reputation reputation = new Reputation(address(this));
        bytes32 agentId = keccak256("agent");

        reputation.applyDelta(agentId, 3, keccak256("positive"));
        reputation.applyDelta(agentId, -1, keccak256("negative"));

        Reputation.ReputationRecord memory record = reputation.getReputation(agentId);
        assert(record.score == 2);
        assert(record.positiveEvents == 1);
        assert(record.negativeEvents == 1);
    }
}
