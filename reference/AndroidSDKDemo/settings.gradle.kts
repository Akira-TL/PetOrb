import java.util.Properties

pluginManagement {
    repositories {
        maven { url = uri("https://maven.aliyun.com/repository/google/") }
        maven { url = uri("https://maven.aliyun.com/repository/gradle-plugin/") }
        maven { url = uri("https://maven.aliyun.com/repository/public/") }
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        mavenLocal()
        maven { url = uri("https://maven.aliyun.com/repository/public/") }
        maven { url = uri("https://jitpack.io") }
        val instaUser = System.getenv("INSTA360_MAVEN_USERNAME")
        val instaPassword = System.getenv("INSTA360_MAVEN_PASSWORD")
        maven {
            url = uri("https://androidsdk.insta360.com/repository/maven-public/")
            if (!instaUser.isNullOrBlank() && !instaPassword.isNullOrBlank()) {
                credentials {
                    username = instaUser
                    password = instaPassword
                }
            }
        }
    }
}

rootProject.name = "AndroidSDKDemo"
include(":app")
