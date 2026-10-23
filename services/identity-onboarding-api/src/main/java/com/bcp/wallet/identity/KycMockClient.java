package com.bcp.wallet.identity;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import org.eclipse.microprofile.rest.client.inject.RegisterRestClient;

@RegisterRestClient(configKey = "kyc-mock")
@Consumes(MediaType.APPLICATION_JSON)
public interface KycMockClient {
    @POST
    @Path("/kyc/verifications")
    Response createVerification(JsonNode request);

    @GET
    @Path("/kyc/verifications/{id}")
    Response getVerification(@PathParam("id") String id);

    @POST
    @Path("/kyc/verifications/{id}/decision")
    Response decideVerification(@PathParam("id") String id, JsonNode request);

    @GET
    @Path("/wallets/{id}")
    Response getWallet(@PathParam("id") String id);
}