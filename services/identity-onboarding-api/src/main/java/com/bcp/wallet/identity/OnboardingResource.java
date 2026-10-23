package com.bcp.wallet.identity;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.eclipse.microprofile.rest.client.inject.RestClient;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;
import java.util.Set;
import java.util.function.Supplier;

@Path("/api/v1")
@Produces(MediaType.APPLICATION_JSON)
public class OnboardingResource {
    private static final Set<String> KYC_SCENARIOS = Set.of(
            "APPROVED", "REJECTED", "MANUAL_REVIEW", "UNAVAILABLE");
    private static final Set<String> KYC_DECISIONS = Set.of("ACTIVE", "REJECTED");

    @Inject
    @RestClient
    KycMockClient kycClient;

    @ConfigProperty(name = "identity.operator.key", defaultValue = "")
    String operatorKey;

    @GET
    @Path("/health")
    public Response health() {
        return Response.ok(Map.of("status", "UP", "service", "identity-onboarding-api")).build();
    }

    @POST
    @Path("/kyc/verifications")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response createVerification(JsonNode request) {
        if (request == null || !request.hasNonNull("documentType") || !request.hasNonNull("document")) {
            return Response.status(Response.Status.BAD_REQUEST)
                    .entity(Map.of("error", "DOCUMENT_FIELDS_REQUIRED"))
                    .build();
        }
        JsonNode documentType = request.get("documentType");
        if (!documentType.isTextual() || !documentType.asText().equals("TEST")) {
            return Response.status(Response.Status.BAD_REQUEST)
                .entity(Map.of("error", "INVALID_DOCUMENT_TYPE"))
                .build();
        }
        JsonNode document = request.get("document");
        if (!document.isTextual() || document.asText().isBlank()
            || document.asText().length() > 200 || !document.asText().startsWith("TEST-")) {
            return Response.status(Response.Status.BAD_REQUEST)
                .entity(Map.of("error", "INVALID_DOCUMENT"))
                .build();
        }
        JsonNode scenario = request.get("scenario");
        if (scenario != null && (!scenario.isTextual() || scenario.asText().isBlank()
            || scenario.asText().length() > 200 || !KYC_SCENARIOS.contains(scenario.asText()))) {
            return Response.status(Response.Status.BAD_REQUEST)
                .entity(Map.of("error", "INVALID_SCENARIO"))
                .build();
        }
        return forward(() -> kycClient.createVerification(request));
    }

    @GET
    @Path("/kyc/verifications/{id}")
    public Response getVerification(@PathParam("id") String id) {
        return forward(() -> kycClient.getVerification(id));
    }

    @POST
    @Path("/kyc/verifications/{id}/decision")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response decideVerification(@PathParam("id") String id,
                                       @HeaderParam("X-Operator-Key") String providedKey,
                                       JsonNode request) {
        if (operatorKey.isBlank() || operatorKey.equals("disabled")) {
            return Response.status(Response.Status.SERVICE_UNAVAILABLE)
                    .entity(Map.of("error", "OPERATOR_ACTION_DISABLED"))
                    .build();
        }
        if (providedKey == null || !MessageDigest.isEqual(
                operatorKey.getBytes(StandardCharsets.UTF_8),
                providedKey.getBytes(StandardCharsets.UTF_8))) {
            return Response.status(Response.Status.FORBIDDEN)
                    .entity(Map.of("error", "FORBIDDEN"))
                    .build();
        }
        if (request == null || !request.hasNonNull("decision")) {
            return Response.status(Response.Status.BAD_REQUEST)
                    .entity(Map.of("error", "DECISION_REQUIRED"))
                    .build();
        }
        JsonNode decision = request.get("decision");
        if (!decision.isTextual() || decision.asText().length() > 200
            || !KYC_DECISIONS.contains(decision.asText())) {
            return Response.status(Response.Status.BAD_REQUEST)
                .entity(Map.of("error", "INVALID_DECISION"))
                .build();
        }
        return forward(() -> kycClient.decideVerification(id, request));
    }

    @GET
    @Path("/wallets/{id}")
    public Response getWallet(@PathParam("id") String id) {
        return forward(() -> kycClient.getWallet(id));
    }

    private Response forward(Supplier<Response> request) {
        Response upstreamResponse;
        try {
            upstreamResponse = request.get();
        } catch (jakarta.ws.rs.WebApplicationException error) {
            upstreamResponse = error.getResponse();
        }
        Response upstream = upstreamResponse;
        try (upstream) {
            Response.ResponseBuilder response = Response.status(upstream.getStatus());
            if (upstream.hasEntity()) {
                response.entity(upstream.readEntity(String.class));
            }
            if (upstream.getMediaType() != null) {
                response.type(upstream.getMediaType());
            }
            return response.build();
        } catch (jakarta.ws.rs.ProcessingException error) {
            return Response.status(Response.Status.BAD_GATEWAY)
                    .entity(Map.of("error", "KYC_PROVIDER_UNAVAILABLE"))
                    .build();
        }
    }
}