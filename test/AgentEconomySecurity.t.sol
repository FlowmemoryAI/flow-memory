// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import "../contracts/TaskEscrow.sol";
import "../contracts/TaskMarketplace.sol";
import "../contracts/Reputation.sol";
import "../contracts/AttestationRegistry.sol";
import "../contracts/DelegationRegistry.sol";
import "../contracts/DisputeResolver.sol";
import "../contracts/SlashingRegistry.sol";
import "../contracts/AgentTreasury.sol";
import "../contracts/CapabilityRegistry.sol";

contract SecurityActor {
    function escrowAssign(TaskEscrow escrow, uint256 taskId, address agent) external {
        escrow.assign(taskId, agent);
    }

    function escrowSettle(TaskEscrow escrow, uint256 taskId, bytes32 resultHash) external {
        escrow.settle(taskId, resultHash);
    }

    function marketplaceClose(TaskMarketplace marketplace, uint256 taskId) external {
        marketplace.close(taskId);
    }

    function reputationDelta(Reputation reputation, bytes32 agentId, int256 delta) external {
        reputation.applyDelta(agentId, delta, keccak256("unauthorized"));
    }

    function resolveDispute(DisputeResolver resolver, uint256 disputeId) external {
        resolver.resolveDispute(disputeId, keccak256("bad"));
    }

    function slash(SlashingRegistry registry, address agent) external {
        registry.recordSlash(agent, 1, keccak256("bad"));
    }

    function credit(AgentTreasury treasury, address agent) external {
        treasury.controllerCredit(agent, 1);
    }
}

contract AgentEconomySecurityTest {
    function testEscrowRejectsUnauthorizedAssignAndSettle() external {
        TaskEscrow escrow = new TaskEscrow();
        SecurityActor actor = new SecurityActor();
        uint256 taskId = escrow.createTask{value: 1 ether}(keccak256("task"));

        try actor.escrowAssign(escrow, taskId, address(0xBEEF)) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("not requester")));
        }

        escrow.assign(taskId, address(0xBEEF));
        try actor.escrowSettle(escrow, taskId, keccak256("result")) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("not requester")));
        }
    }

    function testEscrowRejectsDoubleSettlementInvariant() external {
        TaskEscrow escrow = new TaskEscrow();
        uint256 taskId = escrow.createTask{value: 1 ether}(keccak256("task"));
        escrow.assign(taskId, address(0xBEEF));
        escrow.settle(taskId, keccak256("result"));

        try escrow.settle(taskId, keccak256("second")) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("not assigned")));
        }
        (, , , TaskEscrow.Status status, , ) = escrow.tasks(taskId);
        assert(uint256(status) == uint256(TaskEscrow.Status.Settled));
    }

    function testMarketplaceRejectsUnauthorizedCloseAndOverpricedBid() external {
        TaskMarketplace marketplace = new TaskMarketplace();
        SecurityActor actor = new SecurityActor();
        uint256 taskId = marketplace.postTask(10, keccak256("task"));

        try marketplace.postBid(taskId, 11, keccak256("too-high")) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("price too high")));
        }

        marketplace.postBid(taskId, 9, keccak256("ok"));
        marketplace.assign(taskId, 0);
        try actor.marketplaceClose(marketplace, taskId) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("not requester")));
        }
    }

    function testAuthorityContractsRejectUnauthorizedCalls() external {
        SecurityActor actor = new SecurityActor();
        Reputation reputation = new Reputation(address(this));
        DisputeResolver resolver = new DisputeResolver(address(this));
        SlashingRegistry slashing = new SlashingRegistry(address(this));
        AgentTreasury treasury = new AgentTreasury(address(this));
        uint256 disputeId = resolver.openDispute(address(0xCAFE), 1, keccak256("evidence"));

        try actor.reputationDelta(reputation, keccak256("agent"), 1) {
            assert(false);
        } catch {
            assert(true);
        }
        try actor.resolveDispute(resolver, disputeId) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("not resolver")));
        }
        try actor.slash(slashing, address(0xBAD)) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("not authority")));
        }
        try actor.credit(treasury, address(0xBEEF)) {
            assert(false);
        } catch {
            assert(true);
        }
    }

    function testInvalidRegistryInputsRejected() external {
        AttestationRegistry attestations = new AttestationRegistry();
        DelegationRegistry delegations = new DelegationRegistry();
        CapabilityRegistry capabilities = new CapabilityRegistry();

        try attestations.createAttestation(address(0), keccak256("schema"), keccak256("evidence")) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("invalid subject")));
        }
        try delegations.createDelegation(address(0), keccak256("terms")) {
            assert(false);
        } catch Error(string memory reason) {
            assert(keccak256(bytes(reason)) == keccak256(bytes("invalid delegate")));
        }
        try capabilities.setCapability(keccak256("agent"), keccak256("capability"), bytes32(0), "uri", true) {
            assert(false);
        } catch {
            assert(true);
        }
    }
}
