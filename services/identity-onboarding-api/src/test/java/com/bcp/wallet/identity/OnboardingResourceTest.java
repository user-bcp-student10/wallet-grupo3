package com.bcp.wallet.identity;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.equalTo;

@QuarkusTest
class OnboardingResourceTest {
    @Test
    void reportsLocalHealthWithoutCallingUpstream() {
        given()
                .when().get("/api/v1/health")
                .then()
                .statusCode(200)
                .body("status", equalTo("UP"))
                .body("service", equalTo("identity-onboarding-api"));
    }

    @Test
    void validatesRequiredFieldsBeforeCallingKycProvider() {
        given()
                .contentType("application/json")
                .body("{}")
                .when().post("/api/v1/kyc/verifications")
                .then()
                .statusCode(400)
                .body("error", equalTo("DOCUMENT_FIELDS_REQUIRED"));
    }

    @Test
    void rejectsNonTestDocumentType() {
        given()
                .contentType("application/json")
                .body("{\"documentType\":\"DNI\",\"document\":\"TEST-001\"}")
                .when().post("/api/v1/kyc/verifications")
                .then()
                .statusCode(400)
                .body("error", equalTo("INVALID_DOCUMENT_TYPE"));
    }

    @Test
    void rejectsDocumentWithoutTestPrefix() {
        given()
                .contentType("application/json")
                .body("{\"documentType\":\"TEST\",\"document\":\"12345678\"}")
                .when().post("/api/v1/kyc/verifications")
                .then()
                .statusCode(400)
                .body("error", equalTo("INVALID_DOCUMENT"));
    }

    @Test
    void rejectsUnsupportedScenario() {
        given()
                .contentType("application/json")
                .body("{\"documentType\":\"TEST\",\"document\":\"TEST-001\",\"scenario\":\"OTHER\"}")
                .when().post("/api/v1/kyc/verifications")
                .then()
                .statusCode(400)
                .body("error", equalTo("INVALID_SCENARIO"));
    }

    @Test
    void protectsHumanDecisionWithOperatorKey() {
        given()
                .contentType("application/json")
                .header("X-Operator-Key", "wrong-key")
                .body("{\"decision\":\"ACTIVE\"}")
                .when().post("/api/v1/kyc/verifications/kyc-id/decision")
                .then()
                .statusCode(403)
                .body("error", equalTo("FORBIDDEN"));
    }

    @Test
    void validatesHumanDecisionEnum() {
        given()
                .contentType("application/json")
                .header("X-Operator-Key", "test-operator")
                .body("{\"decision\":\"APPROVED\"}")
                .when().post("/api/v1/kyc/verifications/kyc-id/decision")
                .then()
                .statusCode(400)
                .body("error", equalTo("INVALID_DECISION"));
    }
}