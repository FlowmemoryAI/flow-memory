// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title DelegationRegistry
/// @notice Local unaudited delegation tracker for agent economy v2 tasks.
contract DelegationRegistry {
    enum Status { Active, Completed, Cancelled }

    struct Delegation {
        address delegator;
        address delegate;
        bytes32 termsHash;
        bytes32 completionHash;
        Status status;
    }

    uint256 public nextDelegationId = 1;
    mapping(uint256 => Delegation) public delegations;

    event DelegationCreated(uint256 indexed delegationId, address indexed delegator, address indexed delegate, bytes32 termsHash);
    event DelegationCompleted(uint256 indexed delegationId, address indexed caller, bytes32 completionHash);
    event DelegationCancelled(uint256 indexed delegationId, address indexed delegator);

    function createDelegation(address delegate, bytes32 termsHash) external returns (uint256 delegationId) {
        require(delegate != address(0), "invalid delegate");
        require(termsHash != bytes32(0), "invalid terms");

        delegationId = nextDelegationId++;
        delegations[delegationId] = Delegation({
            delegator: msg.sender,
            delegate: delegate,
            termsHash: termsHash,
            completionHash: bytes32(0),
            status: Status.Active
        });

        emit DelegationCreated(delegationId, msg.sender, delegate, termsHash);
    }

    function completeDelegation(uint256 delegationId, bytes32 completionHash) external {
        Delegation storage delegation = delegations[delegationId];
        require(delegation.delegator != address(0), "missing delegation");
        require(msg.sender == delegation.delegator || msg.sender == delegation.delegate, "not participant");
        require(delegation.status == Status.Active, "not active");
        require(completionHash != bytes32(0), "invalid completion");

        delegation.completionHash = completionHash;
        delegation.status = Status.Completed;
        emit DelegationCompleted(delegationId, msg.sender, completionHash);
    }

    function cancelDelegation(uint256 delegationId) external {
        Delegation storage delegation = delegations[delegationId];
        require(delegation.delegator != address(0), "missing delegation");
        require(msg.sender == delegation.delegator, "not delegator");
        require(delegation.status == Status.Active, "not active");

        delegation.status = Status.Cancelled;
        emit DelegationCancelled(delegationId, msg.sender);
    }
}
