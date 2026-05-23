// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title Flow Memory Marketplace
/// @notice Minimal task marketplace events and task metadata registry.
contract Marketplace {
    struct TaskListing {
        address requester;
        uint256 reward;
        string specURI;
        bool open;
    }

    uint256 public nextListingId = 1;
    mapping(uint256 => TaskListing) public listings;

    event ListingCreated(uint256 indexed listingId, address indexed requester, uint256 reward, string specURI);
    event BidPlaced(uint256 indexed listingId, address indexed agent, uint256 price, string manifestURI);
    event ListingClosed(uint256 indexed listingId);

    error NotRequester();
    error ListingClosedError();

    function createListing(string calldata specURI) external payable returns (uint256 listingId) {
        listingId = nextListingId++;
        listings[listingId] = TaskListing({requester: msg.sender, reward: msg.value, specURI: specURI, open: true});
        emit ListingCreated(listingId, msg.sender, msg.value, specURI);
    }

    function bid(uint256 listingId, uint256 price, string calldata manifestURI) external {
        if (!listings[listingId].open) revert ListingClosedError();
        emit BidPlaced(listingId, msg.sender, price, manifestURI);
    }

    function close(uint256 listingId) external {
        TaskListing storage listing = listings[listingId];
        if (listing.requester != msg.sender) revert NotRequester();
        listing.open = false;
        emit ListingClosed(listingId);
    }
}
