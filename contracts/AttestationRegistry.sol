// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title AttestationRegistry
/// @notice Local unaudited registry for agent economy attestations. No token, chain deployment, or audit assumptions.
contract AttestationRegistry {
    struct Attestation {
        address issuer;
        address subject;
        bytes32 schemaHash;
        bytes32 evidenceHash;
        uint64 issuedAt;
        bool revoked;
    }

    uint256 public nextAttestationId = 1;
    mapping(uint256 => Attestation) public attestations;

    event AttestationCreated(
        uint256 indexed attestationId,
        address indexed issuer,
        address indexed subject,
        bytes32 schemaHash,
        bytes32 evidenceHash
    );
    event AttestationRevoked(uint256 indexed attestationId, address indexed issuer);

    function createAttestation(address subject, bytes32 schemaHash, bytes32 evidenceHash) external returns (uint256 attestationId) {
        require(subject != address(0), "invalid subject");
        require(schemaHash != bytes32(0), "invalid schema");
        require(evidenceHash != bytes32(0), "invalid evidence");

        attestationId = nextAttestationId++;
        attestations[attestationId] = Attestation({
            issuer: msg.sender,
            subject: subject,
            schemaHash: schemaHash,
            evidenceHash: evidenceHash,
            issuedAt: uint64(block.timestamp),
            revoked: false
        });

        emit AttestationCreated(attestationId, msg.sender, subject, schemaHash, evidenceHash);
    }

    function revokeAttestation(uint256 attestationId) external {
        Attestation storage attestation = attestations[attestationId];
        require(attestation.issuer != address(0), "missing attestation");
        require(msg.sender == attestation.issuer, "not issuer");
        require(!attestation.revoked, "already revoked");

        attestation.revoked = true;
        emit AttestationRevoked(attestationId, msg.sender);
    }
}
