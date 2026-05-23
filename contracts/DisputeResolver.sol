// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title DisputeResolver
/// @notice Local unaudited dispute log with a single resolver authority.
contract DisputeResolver {
    enum Status { Open, Resolved }

    struct Dispute {
        address opener;
        address respondent;
        uint256 targetId;
        bytes32 evidenceHash;
        bytes32 outcomeHash;
        Status status;
    }

    address public immutable resolver;
    uint256 public nextDisputeId = 1;
    mapping(uint256 => Dispute) public disputes;

    event DisputeOpened(
        uint256 indexed disputeId,
        address indexed opener,
        address indexed respondent,
        uint256 targetId,
        bytes32 evidenceHash
    );
    event DisputeResolved(uint256 indexed disputeId, address indexed resolver, bytes32 outcomeHash);

    constructor(address resolver_) {
        require(resolver_ != address(0), "invalid resolver");
        resolver = resolver_;
    }

    function openDispute(address respondent, uint256 targetId, bytes32 evidenceHash) external returns (uint256 disputeId) {
        require(respondent != address(0), "invalid respondent");
        require(evidenceHash != bytes32(0), "invalid evidence");

        disputeId = nextDisputeId++;
        disputes[disputeId] = Dispute({
            opener: msg.sender,
            respondent: respondent,
            targetId: targetId,
            evidenceHash: evidenceHash,
            outcomeHash: bytes32(0),
            status: Status.Open
        });

        emit DisputeOpened(disputeId, msg.sender, respondent, targetId, evidenceHash);
    }

    function resolveDispute(uint256 disputeId, bytes32 outcomeHash) external {
        require(msg.sender == resolver, "not resolver");
        Dispute storage dispute = disputes[disputeId];
        require(dispute.opener != address(0), "missing dispute");
        require(dispute.status == Status.Open, "already resolved");
        require(outcomeHash != bytes32(0), "invalid outcome");

        dispute.outcomeHash = outcomeHash;
        dispute.status = Status.Resolved;
        emit DisputeResolved(disputeId, msg.sender, outcomeHash);
    }
}
