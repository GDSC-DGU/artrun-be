package com.artrun.server.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class TrackResponse {
    private String sessionId;
    private String routeId;
    private String status;
    private boolean onRoute;
    private Integer completionRate;
    private Integer distanceTraveledMeters;
    private Integer distanceRemainingMeters;
    private Integer offRouteDistanceMeters;
    private Integer nearestRoutePointIndex;
    private InstructionDto currentInstruction;
    private InstructionDto nextInstruction;
    private CheckpointDto passedCheckpoint;
    private VoiceCueDto voiceCue;
    private PaceFeedbackDto paceFeedback;
    private EdmControlDto edmControl;
    private String warningMessage;

    @Getter
    @Builder
    @AllArgsConstructor
    public static class InstructionDto {
        private String instructionId;
        private String type;
        private String message;
        private int distanceToInstructionMeters;
        private LatLng point;
    }

    @Getter
    @Builder
    @AllArgsConstructor
    public static class CheckpointDto {
        private String checkpointId;
        private int sequence;
        private String name;
        private LatLng point;
    }

    @Getter
    @Builder
    @AllArgsConstructor
    public static class VoiceCueDto {
        private boolean shouldSpeak;
        private String priority;
        private String message;
        private String cueType;
        private String speakKey;
    }

    @Getter
    @Builder
    @AllArgsConstructor
    public static class PaceFeedbackDto {
        private int targetPaceSecPerKm;
        private int currentPaceSecPerKm;
        private String paceStatus;
        private String message;
    }

    @Getter
    @Builder
    @AllArgsConstructor
    public static class EdmControlDto {
        private boolean enabled;
        private int currentBpm;
        private int targetBpm;
        private String action;
        private String reason;
    }

    @Getter
    @Builder
    @AllArgsConstructor
    public static class LatLng {
        private double lat;
        private double lng;
    }
}
