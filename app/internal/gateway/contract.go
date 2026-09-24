package gateway

import fabricgateway "github.com/hyperledger/fabric-gateway/pkg/client"

const (
	channelName   = "supplychannel"
	chaincodeName = "supplycc"
)

func SupplyContract(gateway *fabricgateway.Gateway) *fabricgateway.Contract {
	return gateway.GetNetwork(channelName).GetContract(chaincodeName)
}
